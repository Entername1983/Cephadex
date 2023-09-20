import uuid
import datetime as dt

from flask import (
    Blueprint, render_template, url_for,
    Response, send_file, jsonify, flash, redirect, request, session
)
from flask_login import login_required, current_user
from sqlalchemy.sql import or_, insert
from bleach import clean

from models.models_ import (
    Card, Deck, DeckFiles, SharedDecks,
    Test, UserSettings, User, deck_relationships, DeckAttributes, Game
)
####from cardcreator import create_image, creator
from models.creators.formatters import create_pdf 
from models.creators.creator import AiCaller
from models.helpers.helpers import apology
from models.anki import (
    request_anki_permission, anki_create_deck,
    anki_create_card, find_notes, check_anki_connect
)
from models.tracking.events import event_tracker
## FORMS
from models.forms.forms import (
    DeckOrg, SearchAndSortForm, Share, UpdateFileNameForm
)
from models.send_email import send_email
from models.qr_code import create_qr_code

from config.settings import APP_URL
from run.extensions import db

from models.helpers.log_decorators import log_decorator


deck_bp = Blueprint(
    'deck_bp', 
    __name__,
    template_folder='templates/deck_bp',
    static_folder='static'
)



@deck_bp.route("/view_decks", methods = ["GET", "POST"])
@login_required
@log_decorator
def view_decks():
    """ main view once logged in"""
    share_form = Share()
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings is None:
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
   ## check if user has any pending quizzes
    quizzes = Test.query.filter(Test.taker.contains(current_user)).all()
    user = current_user
    email = current_user.email
    shared_decks = (
            SharedDecks.query
            .filter(SharedDecks.receiver == current_user.id).all()
    )
    
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Items per page
    sort_by = request.args.get('sort_by', 'time_created')
    order = request.args.get('order', 'asc')
    sort_method = request.args.get('sort', None)

    search_query = request.args.get('search', None)
    query = Deck.query.filter(Deck.user_id == current_user.id)

    if search_query:
        query = query.filter(Deck.name.ilike(f'%{search_query}%'))

    if sort_by:
        if order == 'asc':
            query = query.order_by(getattr(Deck, sort_by).asc())
        else:
            query = query.order_by(getattr(Deck, sort_by).desc())

    decks_paginated = query.paginate(page, per_page, False)

    return render_template('deck_bp/view_decks.html', decks=decks_paginated.items, decks_paginated=decks_paginated, 
            shared_decks = shared_decks,quizzes=quizzes, user = user, settings = user_settings, share_form = share_form)







@deck_bp.route("/createdeck", methods = ["GET", "POST"])
@login_required
@log_decorator
def create_deck():
    """ deprecated route """
    return render_template("deck_bp/createdeck.html", title="Create Deck")

@deck_bp.route("/delete/<int:id>", methods=["DELETE"])
@login_required
@log_decorator
def delete(id):
    deck_to_delete = Deck.query.get_or_404(id)
    deck_attributes = DeckAttributes.query.filter_by(deck_id = id ).all()
    games_to_delete = Game.query.filter_by(deck_id = id).all()
    if current_user.id != deck_to_delete.user_id:
        return jsonify({'error': 'Deck not assigned to user'}), 403
    for attribute in deck_attributes:
        db.session.delete(attribute)
    for game in games_to_delete:
        db.session.delete(game)
    db.session.delete(deck_to_delete)
    db.session.commit()
    return jsonify({'message': 'Deck deleted successfully'})

@deck_bp.route("/rename_deck/<int:id>/<string:new_name>", methods = ["POST", "GET"])
@login_required
@log_decorator
def rename_deck(id, new_name):
    c_id = id
    c_new_name = clean(new_name)
    deck = Deck.query.get_or_404(c_id)
    if(current_user.id != deck.user_id):
        return jsonify({'error': 'Deck not assigned to user'}), 403
    deck.rename(clean(c_new_name))
    db.session.commit()
    return redirect(url_for('deck_bp.view_decks'))

@deck_bp.route("/deletecard/<int:deck_id>/<int:card_id>", methods = ["POST"])
@login_required
@log_decorator
def deletecard(deck_id, card_id):
    c_deck_id = deck_id
    c_card_id = card_id
    deck = Deck.query.get_or_404(c_deck_id)
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    card_to_delete = Card.query.get_or_404(c_card_id)
    if card_to_delete != None:
        db.session.delete(card_to_delete)
        db.session.commit()
        return jsonify({"status": "success", "message": "Card deleted"})
    else:
        return jsonify({"status": "error", "message": "Card not found"})

@deck_bp.route("/downloadascsv/<int:deck_id>", methods = ["POST", "GET"])
@login_required
@log_decorator
def downloadascsv(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "downloadascsv")
    deck = Deck.query.filter_by(id=c_deck_id).first()
    if(current_user.id != deck.user_id):
       return jsonify({'error': 'Deck not assigned to user'}), 403
    termsstrings = []
    for card in deck.cards:
        if card.boc_2 is None:
            card.boc_2 = "null"
        if card.boc_3 is None:
            card.boc_3 = "null"
        if card.boc_4 is None:
            card.boc_4 = "null"
        ## replace commas with semicolons
        fields = [card.term, card.content, card.boc_2,
                card.boc_3, card.boc_4, card.category]
        string = ",".join(field.replace(",", ";") for field in fields) + "\n"
        termsstrings.append(string)
    csvstring = "".join(termsstrings)
    return Response(csvstring, mimetype="text/csv")

@deck_bp.route("/regenerate_def", methods = ["POST", "GET"])
@login_required
@log_decorator
def regenerate_def():
    event_tracker(current_user.id, "regenerate_def")
    card_id = clean(request.form["id"])
    card = Card.query.filter(Card.id==card_id).first()
    prompt_options = process_prompt_options_regen(card)
    term = card.term 
    open_ai_caller = AiCaller()
    content = open_ai_caller.regenerate_definition(term, prompt_options)[0]
    card.content = content
    try:
        db.session.commit()
    except Exception as e:
        raise e
    return jsonify({'content': content})

def process_prompt_options_regen(card):
    if card.prompt_option is None:
        card.prompt_option = "Definitions"
    return {
        'main_opt': card.prompt_option,
        'subject_opt': card.prompt_option2,
        'trans_opt': card.trans_option,
        'lang_opt': card.trans_option,
        'detail_lvl_opt': card.len_option,
    }

def create_parent_child_relationship(parent_deck_id, child_deck_id):
    new_relationship = insert(deck_relationships).values(parent_deck=parent_deck_id,
                    child_deck=child_deck_id)
    session.execute(new_relationship)
    session.commit()


@deck_bp.route("/add_card/<int:deck_id>", methods=["POST"])
@login_required
@log_decorator
def add_card(deck_id):
    form = DeckOrg(request.form)
    print("entered add new card")
    if form.validate_on_submit():
        entry = Card(
            term=form.new_term.data,
            content=form.new_content.data,
            boc_2=form.new_boc_2.data,
            boc_3=form.new_boc_3.data,
            boc_4=form.new_boc_4.data,
            category=form.new_category.data,
            time_created=dt.datetime.now(dt.timezone.utc),
        )
        deck = Deck.query.filter_by(id=deck_id, user_id=current_user.id).first()
        if deck:
            deck.cards.append(entry)
            db.session.commit()
            return jsonify(success=True)
    return jsonify(success=False)

@deck_bp.route("/edit_card_new", methods=["POST"])
@login_required
@log_decorator
def edit_card_new():
    data = request.get_json()
    if data:
        card_id = data["id"]
        card = Card.query.filter_by(id=card_id).first()
        if 'term' in data:
            term = data["term"]
            card.term = term
        if 'content' in data:
            if data["content"] != "":
                content = data["content"]
                card.content = content
        if 'boc_2' in data:
            boc_2 = data["boc_2"]
            card.boc_2 = boc_2
        if 'boc_3' in data:
            boc_3 = data["boc_3"]
            card.boc_3 = boc_3
        if 'boc_4' in data:
            boc_4 = data["boc_4"]
            card.boc_4 = boc_4
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False)


# @deck_bp.route("/carousel/<int:deck_id>", methods = ["GET", "POST"])
# @login_required
# @log_decorator
# def carousel(deck_id):
    
#     c_deck_id = deck_id
#     deck = Deck.query.filter_by(id=c_deck_id, user_id=current_user.id).first()

#     form = DeckOrg(obj=deck)
#     cards = (
#             Card.query.filter(Card.decks_backref.any(id=deck_id))
#             .order_by(Card.id.desc()).all()
#     )
#     if(current_user.id != deck.user_id):
#          return apology('Deck not assigned to user', 403)
#     return render_template("/deck_bp/carousel.html", title="Carousel",
#                             deck=deck, cards=cards, form=form)
@deck_bp.route("/card_viewer/<int:deck_id>", methods = ["GET", "POST"])
@login_required
@log_decorator
def card_viewer(deck_id):
    page = request.args.get('page', 1, type=int)
    per_page = 4  # Items per page
    c_deck_id = deck_id
    deck = Deck.query.filter_by(id=c_deck_id, user_id=current_user.id).first()

    form = DeckOrg(obj=deck)
    paginated_cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.id.desc()).paginate(page, per_page, False)
    )
    print(paginated_cards.items)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    return render_template("/deck_bp/card_viewer.html", title="Card viewer",
                            deck=deck, paginated_cards=paginated_cards, form=form)
"""
    if form.validate_on_submit():
        print("entered validate on submit")
        if form.term.data:
            print("form term data")
            term = form.term.data
            print(term)
            content = form.content.data
            boc_2 = form.boc_2.data
            boc_3 = form.boc_3.data
            boc_4 = form.boc_4.data
            id = form.id.data
            formula = form.formula.data
            card = Card.query.filter_by(id=id).first()
            if term != "":
                if card.term != None:
                    card.term = term.strip()
            if content != "":
                if card.content != None:
                    card.content = content.strip()
            if boc_2 != "":
                if boc_2 != None:
                    card.boc_2 = boc_2.strip()
            if boc_3 != "":
                if boc_3 != None:
                    card.boc_3 = boc_3.strip()
            if boc_4 != "":
                if boc_4 != None:
                    card.boc_4 = boc_4.strip()
            if formula != "":
                if formula != None:
                    card.formula = formula.strip()
            db.session.commit()
"""

## OBSOLETE?
@deck_bp.route("/edit_card", methods=["POST"])
@login_required
@log_decorator
def edit_card():
    form = DeckOrg(request.form)
    if form.validate():
        id = form.id.data
        card = Card.query.filter_by(id=id).first()
        if card:
            card.term = form.term.data.strip()
            card.content = form.content.data.strip()
            card.boc_2 = form.boc_2.data.strip()
            card.boc_3 = form.boc_3.data.strip()
            card.boc_4 = form.boc_4.data.strip()
            if card.formula:
                card.formula = form.formula.data.strip()
            db.session.commit()
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Card not found"}), 404
    else:
        return jsonify({"status": "error", "message": "Invalid form data"}), 400
    


@deck_bp.route("/import_public_deck/<int:deck_id>", methods = ["GET", "POST"])
@login_required
@log_decorator
def import_public_deck(deck_id):
    c_deck_id = deck_id
    deck = Deck.query.filter_by(id=c_deck_id, public=True).first()
    if deck is None:
        return apology("Deck not found", 404)
    else:
        new_deck = Deck(user_id = current_user.id,
                    name="Copy of " + deck.name,
                    description=deck.description,
                    shared=True,
                    time_created=dt.datetime.now(dt.timezone.utc))
        db.session.add(new_deck)
        for card in deck.cards:
            new_card = Card(term=card.term, content=card.content,
                            boc_2=card.boc_2, boc_3=card.boc_3, boc_4=card.boc_4,
                            img=card.img,sound=card.sound, subject=card.subject,
                            topic=card.topic, category=card.category,
                            prompt_option=card.prompt_option, 
                            prompt_option2=card.prompt_option2,
                            trans_option=card.trans_option,
                            len_option=card.len_option,
                            qmin_option=card.qmin_option,
                            qmax_option=card.qmax_option,
                            diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
        db.session.commit()
    return jsonify({"success": True})






@deck_bp.route("/document_viewer/<int:deck_id>", methods=["GET", "POST"])
@login_required
@log_decorator
def document_viewer(deck_id):
    form = UpdateFileNameForm()
    search_and_sort_form = SearchAndSortForm()

    ## GET DECK
    deck = Deck.query.get_or_404(deck_id)
    ## GET source files
    files = deck.deck_files
    if deck.user_id != current_user.id:
        return apology("You do not have permission to view this deck", 403)
    ##files = DeckFiles.query.filter(DeckFiles.decks.any(id=deck_id)).order_by
    # (DeckFiles.file_name.desc()).all()
    if request.method == 'GET':
        search_query = None
        sort_method = search_and_sort_form.sort.data
        search_query = request.args.get('search', '')

        if sort_method != 'default':
                if sort_method == 'name_asc':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.file_name.asc())
                            .all()
                        )
                if sort_method == 'name_desc':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.file_name.desc())
                            .all()
                    )
                if sort_method == 'type':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.create_type.asc())
                            .all()
                    )
                if sort_method == 'date':
                    files = (
                            DeckFiles.query
                            .filter(DeckFiles.decks.any(id=deck_id))
                            .order_by(DeckFiles.time_created.desc())
                            .all()
                    )
        elif search_query:
                search_query = search_query.strip()
                files = (
                    DeckFiles.query
                    .filter(DeckFiles.decks.any(id=deck_id))
                    .filter(DeckFiles.file_name.contains(search_query))
                    .all()
                )
        return render_template("deck_bp/document_viewer.html", title="Sea Dox",
                                files=files, deck = deck, form = form,
                                search_form = search_and_sort_form)
    if form.validate():
        file_id = form.file_id.data
        new_name = form.new_name.data
        file = DeckFiles.query.get_or_404(file_id)

        if new_name != '':
            file.file_name = new_name
            db.session.commit()
        return render_template("deck_bp/document_viewer.html",
                                title="Sea Dox", files=files, deck = deck,
                                form = form, search_form = search_and_sort_form)
    return render_template("deck_bp/document_viewer.html", title="Sea Dox",
                            files=files, deck = deck, form = form,
                            search_form = search_and_sort_form)





@deck_bp.route("/source_file/<int:file_id>", methods=["GET", "POST"])
@login_required
@log_decorator
def source_file(file_id):
    c_file_id = file_id
    file = DeckFiles.query.get_or_404(c_file_id)
    return render_template("deck_bp/source_file.html", title="Source File", file=file)

@deck_bp.route("/download_source/<int:file_id>", methods=["GET", "POST"])
@login_required
@log_decorator
def download_source(file_id):
    ## GET FILE
    c_file_id = file_id
    event_tracker(current_user.id, "download_source", c_file_id)
    file = DeckFiles.query.get_or_404(c_file_id)
    name = f"{file.file_name}.pdf"
    text = file.text_string
    ## turn file.text_string into a pdf
    pdf_buffer = create_pdf(text)
    return send_file(pdf_buffer, download_name = name)

@deck_bp.route("/delete_file/<int:deck_id>/<int:file_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def delete_file(deck_id, file_id):
    c_deck_id = deck_id
    c_file_id = file_id
    event_tracker(current_user.id, "delete_file", c_file_id)
    file = DeckFiles.query.get_or_404(c_file_id)
    deck = Deck.query.get_or_404(c_deck_id)
    db.session.delete(file)
    db.session.commit()
    return redirect(("/deck_bp/document_viewer/{deck}").format(deck=deck.id)) 

@deck_bp.route('/generate_link/<int:deck_id>', methods=['GET'])
@login_required
@log_decorator
def generate_link(deck_id):
    print("entered generate link")
    # create a share_id for the deck and store it in the database
    deck = Deck.query.get(deck_id)
    if deck.share_id:
        print("deck already has share_id")

        link = f'{APP_URL}/deck_bp/shared_deck_view/{deck.share_id}'
        img_str = create_qr_code(link)
        return jsonify(
            {
                'share_link': f'{APP_URL}/deck_bp/shared_deck_view/{deck.share_id}',
                'qr_code': img_str,
            }
        )
    else:
        print("deck does not have share_id")
        share_id = str(uuid.uuid4())
        deck.share_id = share_id
        db.session.commit()

        # generate a QR code
        link = f'{APP_URL}/deck_bp/shared_deck_view/{share_id}'
        img_str = create_qr_code(link)

        # return the shared link and QR code
        return jsonify(
            {
                'share_link': f'{APP_URL}/deck_bp/shared_deck_view/{share_id}',
                'qr_code': img_str,
            }
        )


@deck_bp.route('/shared_deck_view/<string:share_id>', methods=['GET'])
@log_decorator
def shared_deck_view(share_id):
    page = request.args.get('page', 1, type=int)
    per_page = 8 
    deck = Deck.query.filter_by(share_id=share_id).first_or_404()
    paginated_cards = (
            Card.query.filter(Card.decks_backref.any(id=deck.id))
            .order_by(Card.term.asc()).paginate(page, per_page, False)
    )
    session['shared_deck_id'] = share_id
    return render_template('deck_bp/shared_deck_view.html', deck=deck, paginated_cards = paginated_cards)


@deck_bp.route("/share_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def share_deck(deck_id):
    c_deck_id = deck_id
    share_form = Share()
    sender_id = current_user.id
    deck_to_copy = Deck.query.get_or_404(c_deck_id)
    if not deck_to_copy.share_id:
        share_id = str(uuid.uuid4())
        deck_to_copy.share_id = share_id
        db.session.commit()

    event_tracker(current_user.id, "share_deck", c_deck_id)

    if share_form.validate_on_submit():
        users_emails = share_form.emails.data.split(",")
        
        for email in users_emails:
            email = email.strip()
            user = User.query.filter_by(email=email).first()

            if user:
                shared_deck = SharedDecks(name="Copy of " + deck_to_copy.name,
                                           description=deck_to_copy.description,
                                            sender=sender_id,
                                            time_created=dt.datetime.now(dt.timezone.utc),
                                            receiver=user.id,
                                              share_id = deck_to_copy.share_id)
                db.session.add(shared_deck)

                for card in deck_to_copy.cards:
                    new_card = Card(term=card.term,
                                    content=card.content, boc_2=card.boc_2,
                                    boc_3=card.boc_3, boc_4=card.boc_4, img=card.img,
                                    sound=card.sound, subject=card.subject,
                                    topic=card.topic, category=card.category,
                                    prompt_option=card.prompt_option,
                                    prompt_option2=card.prompt_option2,
                                    trans_option=card.trans_option,
                                    len_option=card.len_option,
                                    qmin_option=card.qmin_option,
                                    qmax_option=card.qmax_option,
                                    diff_lvl=card.diff_lvl)
                    shared_deck.cards.append(new_card)
                db.session.commit()
            else:
                share_link = APP_URL + '/deck_bp/shared_deck_view/' + deck_to_copy.share_id
                print("sending email to", email)
                send_email(email, None, 'deck_shared', 'Someone sent you a deck', link=share_link)
                pass
        return jsonify('success', 'Deck shared successfully')
    else:
        return jsonify('error', 'Deck not shared')
    
@deck_bp.route("/approve_shared/<int:deck_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def appprove_shared(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "appprove_shared", c_deck_id)
    shared_deck = SharedDecks.query.get_or_404(c_deck_id)
    new_deck = Deck(user_id = current_user.id,
                    name=shared_deck.name,
                    description=shared_deck.description,
                    shared=True, sharer=shared_deck.sender,
                    time_created=dt.datetime.now(dt.timezone.utc))
    db.session.add(new_deck)
    for card in shared_deck.cards:
        new_card = Card(term=card.term,
                         content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
                        boc_4=card.boc_4,img=card.img, sound=card.sound,
                        subject=card.subject, topic=card.topic,
                        category=card.category,
                        prompt_option=card.prompt_option,
                        prompt_option2=card.prompt_option2,
                        trans_option=card.trans_option, len_option=card.len_option,
                        qmin_option=card.qmin_option,
                        qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
        new_deck.cards.append(new_card)
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})

@deck_bp.route("/save_shared_deck/<share_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def save_shared_deck(share_id):
    event_tracker(current_user.id, "deck_bprove_shared", share_id)
    shared_deck = Deck.query.filter_by(share_id=share_id).first_or_404()
    new_deck = Deck(user_id = current_user.id,
                    name=shared_deck.name,
                    description=shared_deck.description,
                    time_created=dt.datetime.now(dt.timezone.utc))
    db.session.add(new_deck)
    for card in shared_deck.cards:
        new_card = Card(term=card.term,
                         content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
                        boc_4=card.boc_4,img=card.img, sound=card.sound,
                        subject=card.subject, topic=card.topic,
                        category=card.category,
                        prompt_option=card.prompt_option,
                        prompt_option2=card.prompt_option2,
                        trans_option=card.trans_option, len_option=card.len_option,
                        qmin_option=card.qmin_option,
                        qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
        new_deck.cards.append(new_card)
    db.session.commit()
    success = True
    return redirect(url_for('deck_bp.deck_manager', deck_id=new_deck.id))

@deck_bp.route("/reject_shared/<int:deck_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def reject_shared(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "reject_shared", c_deck_id)
    shared_deck = SharedDecks.query.get_or_404(c_deck_id)
    shared_deck.delete()
    db.session.commit()
    success = True
    return jsonify({'success': success})


@deck_bp.route("/print_doc/<int:file_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def print_doc(file_id):
    c_file_id = file_id
    source = DeckFiles.query.filter_by(id = c_file_id).first()
    return render_template('deck_bp/print_doc.html',file=source)

@deck_bp.route("/import_deck/", methods=["GET", "POST"])
@login_required
@log_decorator
def import_deck():
    return render_template('/deck_bp/import_deck.html')



@deck_bp.route('/import_anki', methods=['POST'])
@login_required
@log_decorator
def import_anki():
    data = request.json
    for card in data:
        deck_name = clean(card['deckName'])
        card_front = clean(card['fields']['Front']['value'])
        card_back = clean(card['fields']['Back']['value'])
        deck = Deck.query.filter_by(name=deck_name, user_id=current_user.id).first()
        if not deck:
            deck = Deck(name=deck_name, description="anki", user_id=current_user.id)
            db.session.add(deck)
            db.session.commit()
        card_O = Card(term=card_front, content=card_back,
                       srs_interval=card['interval']*1440, category="anki")
        db.session.add(card_O)
        deck.cards.append(card_O)
        db.session.commit()
    flash('Anki deck imported', 'success')
    return jsonify({"success": True})

def quote_deck_name_if_needed(deck_name):
    if ' ' in deck_name:
        return '"{}"'.format(deck_name)
    else:
        return deck_name

@deck_bp.route("/export_deck/<int:deck_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def export_deck(deck_id):
    c_deck_id = deck_id
    try:
        request_anki_permission()
    except Exception as e:
        return apology("Anki did not grant permission")
    if check_anki_connect() == True:
        deck = Deck.query.get_or_404(c_deck_id)
        if deck.user != current_user:
            flash('you are not allowed to view this page', 'danger')
            return redirect('/home/')
        cards = deck.cards
        anki_create_deck(deck.name)
        for card in cards:
            query = card.term
            notes = find_notes(query)
            if notes == False:
                srs_interval = str(int(card.srs_interval/1440))
                anki_create_card(deck.name, card.term, card.content)
        event_tracker(current_user.id, "export-anki", "success")
        flash("Deck exported", "success")
        return redirect(url_for('deck_bp.view_decks'))
    else:
        event_tracker(current_user.id, "export-anki", "fail")

        return apology('Please make sure you are on a desktop, have Anki installed' 
                'running, and  have the AnkiConnect plugin installed and enabled.', 400)
    

@deck_bp.route('/get_deck_data/<int:deck_id>', methods=['GET'])
@login_required
@log_decorator
def get_deck_data(deck_id):
    c_deck_id = deck_id
    deck_name = Deck.query.get_or_404(c_deck_id).name
    cards = Deck.query.get_or_404(c_deck_id).cards
    card_list = []
    for card in cards:
        card_list.append({
            'id': card.id,
            'front': card.term,
            'back': card.content,
            'interval': card.srs_interval
        })
    response = jsonify({
        'name': deck_name,
        'cards': card_list
    })
    return response



@deck_bp.route("/latest_deck", methods=["POST", "GET"])
@login_required
@log_decorator
def latest_deck():
    if not current_user.is_authenticated:
        return "User is not authenticated. Please log in to continue."
    deck = (
            Deck.query
            .filter_by(user_id=current_user.id)
            .order_by(Deck.id.desc()).first()
    )
    return (
        redirect('/deck_bp/deck_manager/{deck_id}'.format(deck_id=deck.id))
        if deck is not None
        else redirect('/deck_bp/view_decks')
    )
    

@deck_bp.route("/public_cards/<int:deck_id>/", methods=['GET', 'POST'])
@login_required
@log_decorator
def public_cards(deck_id):
    page = request.args.get('page', 1, type=int)
    per_page = 12
    deck = Deck.query.filter_by(id=deck_id).first()
    if deck.public is False:
        return apology("Sorry, this deck is not public")
    paginated_cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.term.asc()).paginate(page, per_page, False)
    )
    print(paginated_cards.items)
    return render_template('deck_bp/public_cards.html', paginated_cards = paginated_cards, deck=deck, page = page)


@deck_bp.route("/public_decks", methods = ['GET', 'POST'])
@login_required
@log_decorator
def public_decks():
    form = SearchAndSortForm()

    page = request.args.get('page', 1, type=int)
    per_page = 8  # Items per page
    search_query= form.search.data
    sort_method = form.sort.data
    # Start building the query
    query = Deck.query.filter(Deck.public == True)  # noqa: E712
    # Apply search filters if search_query is present
    if search_query:
        query = query.filter(
            or_(
                Deck.name.ilike(f'%{search_query}%'),
                Deck.description.ilike(f'%{search_query}%'),
                Deck.category.ilike(f'%{search_query}%')
            )
        )
    # Apply sorting if sort_method is not 'default'
    if sort_method == 'name_asc':
        query = query.order_by(Deck.name.asc())
    elif sort_method == 'name_desc':
        query = query.order_by(Deck.name.desc())
    elif sort_method == "category_asc":
        query = query.order_by(Deck.category.asc())
    elif sort_method == "category_desc":
        query = query.order_by(Deck.category.desc())
    decks_paginated = query.paginate(page, per_page, False)


    return render_template('deck_bp/public_decks.html', decks=decks_paginated.items, 
            decks_paginated=decks_paginated, form=form)

@deck_bp.route("/deck_manager/<int:deck_id>", methods=['GET', 'POST'])
@login_required
@log_decorator
def deck_manager(deck_id):
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Items per page
    settings = UserSettings.query.filter_by(user=current_user.id).first()
    form = DeckOrg()
    share_form = Share()
    deck = Deck.query.filter_by(id=deck_id).first()
    if current_user.id != deck.user_id:
        return apology("Sorry, this is not your deck")

    quizzes = Test.query.filter_by(deck_id=deck_id).all()
    paginated_cards = (
            Card.query.filter(Card.decks_backref.any(id=deck_id))
            .order_by(Card.term.asc()).paginate(page, per_page, False)
    )
    print(paginated_cards.items)
    files = deck.deck_files
    if form.validate_on_submit():
        if form.new_deck_name.data:
            deck.name = form.new_deck_name.data
            deck.source = form.new_deck_source.data
            deck.description = form.new_deck_description.data
            deck.subject = form.new_deck_subject.data
            deck.topic = form.new_deck_topic.data
            parent = form.deck_list.data
            public = bool(request.form.get('public'))
            if public:
                deck.public = True
            else:
                deck.public = False
            if parent:
                db.session.execute(deck_relationships.insert().values(parent_deck=parent.id,
                                    child_deck=deck.id))
            db.session.commit()
    return render_template('deck_bp/deck_manager.html', deck=deck, files=files,
                share_form = share_form, quizzes = quizzes, form=form, settings=settings,
                page=page, paginated_cards = paginated_cards)


#### CHAT BOT ####

@deck_bp.route("/explain_further/<int:card_id>/", methods=['GET', 'POST'])
@login_required
@log_decorator
def explain_further(card_id):
    c_card_id = card_id
    card = Card.query.filter_by(id=c_card_id).first()
    if card is None:
        return render_template('404.html')
    ai_caller = AiCaller()
    term = card.term
    subject = card.subject
    content = card.content
    response = ai_caller.explain_more(term, subject, content)
    return {"response": response}

@deck_bp.route("/why_wrong/<int:card_id>/", methods=['GET', 'POST'])
@login_required
@log_decorator
def why_wrong(card_id):
    c_card_id = card_id
    card = Card.query.filter_by(id=c_card_id).first()
    open_ai_caller = AiCaller()
    if card is None:
        return render_template('404.html')
    ww_prompt = why_wrong_builder(c_card_id)
    response = open_ai_caller.why_wrong_generator(ww_prompt)
    return {"response": response}    
    
def why_wrong_builder(card_id):
    card = Card.query.filter_by(id=card_id).first()
    return {
        "term": card.term,
        "subject": card.subject,
        "content": card.content,
        "boc_2": card.boc_2,
        "boc_3": card.boc_3,
        "boc_4": card.boc_4,
        "category": card.category,
        "card_id": card.id,
    }


@deck_bp.route("/send_question/<int:card_id>/", methods=['GET', 'POST'])
@login_required
@log_decorator
def send_question(card_id):
    c_card_id = card_id
    card = Card.query.filter_by(id=c_card_id).first()
    latest_paragraph = clean(request.form.get('latest_paragraph'))
    question = clean(request.form.get('question'))
    term = clean(card.term)
    content = clean(card.content)
    ai_caller = AiCaller()
    response = ai_caller.send_question_generator(term, content, latest_paragraph, question)
    return {"response": response}   