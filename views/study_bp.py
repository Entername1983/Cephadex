import json
import logging
from bleach import clean
from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
####from cardcreator import create_image, creato
from models.helpers.helpers import apology
from models.tracking.events import event_tracker
from models.models_ import Card, Deck, UserSettings
from models.forms.forms import StudyDeckForm
from run.extensions import db

from models.helpers.log_decorators import log_decorator
study_bp = Blueprint(
    'study_bp', 
    __name__,
    template_folder='templates/study_bp',
    static_folder='static'
)

logger = logging.getLogger("flask_app")

NUMBER_OF_CARDS_TO_LOAD = 20

@study_bp.route("/study", methods = ["GET", "POST"])
@login_required
@log_decorator
def study():
    return render_template("study_bp/study.html", title="Study")

@study_bp.route('/study_select', methods=['GET', 'POST'])
@log_decorator
def study_select():
    form = StudyDeckForm()
    try:
        form.deck.choices = [(deck.id, deck.name) for deck in Deck.query.filter_by(user_id=current_user.id).all()]  # noqa: E501
    except Exception as e:
        logger.error(f"Error in study_select: {e}")
        raise e
    if form.validate_on_submit():
        return redirect(url_for('study_bp.study_deck', deck_id=form.deck.data))
    return render_template('study_bp/study_select.html', form=form)


@study_bp.route("/get-due-cards/<deck_id>", methods= ["POST", "GET"])
@login_required
@log_decorator
def get_due_cards(deck_id):
    c_deck_id = deck_id
    deck = Deck.query.get(clean(c_deck_id))
    ## later add in option to modify number of new cards to be shown
    n = NUMBER_OF_CARDS_TO_LOAD
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    return deck.get_due_cards(n)


@study_bp.route("/study_deck/<int:deck_id>", methods = ["POST", "GET"])
@login_required
@log_decorator
def study_deck(deck_id):
    c_deck_id = deck_id
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings is None:
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    event_tracker(current_user.id, "study_deck", c_deck_id)
    deck = Deck.query.get(c_deck_id)
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    return render_template("study_bp/study_deck.html", title="Study deck",
                            deck=deck_id, deck0 = deck,  settings = user_settings) 

@study_bp.route("/update_study_data/<int:deck_id>", methods = ["POST", "GET"])
@login_required
@log_decorator
def update_study_data(deck_id):
    deck0 = Deck.query.get(deck_id)
    total_answered = deck0.total_answered()
    correct_answers = deck0.correct_incorrect()[0]
    if total_answered > 0:
        percentage = (correct_answers / total_answered) * 100
    else:
        percentage = 0    
    cards_due = deck0.cards_due()

    return jsonify({
        'total_answered': total_answered,
        'percentage': f'{percentage:.1f}%',
        'cards_due': cards_due
    })

@study_bp.route("/study_deck_all", methods = ["POST", "GET"])
@login_required
@log_decorator
def study_deck_all():
    event_tracker(current_user.id, "study_deck_all")
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings is None:
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    ## loads all decks for a user
    ## get list of decks for user with id user id
    decks = Deck.query.filter(Deck.user_id == current_user.id).all()
    decks_data = [{'id': deck.id} for deck in decks]
    decks_json = json.dumps(decks_data)
    return render_template('study_bp/study_deck_all.html', title='Study all decks',
                            decks_json=decks_json, decks=decks, settings = user_settings)

@study_bp.route("/increment/<card_id>", methods = ["POST", "GET"])
@login_required
@log_decorator
def increment(card_id):
    c_card_id = card_id
    card = Card.query.get(c_card_id)
    deck = Deck.query.filter(Deck.cards.any(id=c_card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if card is None:
            return apology('Card not found', 404)
    card.increment()
    card.update_time()
    return jsonify({'success': 'Card incremented'}), 200
    

@study_bp.route("/decrement/<card_id>", methods = ["POST"])
@login_required
@log_decorator
def decrement(card_id):
    c_card_id = card_id
    card = Card.query.get(c_card_id)
    deck = Deck.query.filter(Deck.cards.any(id=c_card_id)).first()
    if(current_user.id != deck.user_id):
        return apology('Deck not assigned to user', 403)
    if card is None:
        return apology('Card not found', 404)
    card.decrement()
    card.update_time()
    return jsonify({'success': 'Card decremented'}), 200

@study_bp.route("/forcestudy/<deck_id>")
@log_decorator
def force_study(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "force_study", c_deck_id)
    deck = Deck.query.get(c_deck_id)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    return apology('Deck not found', 404) if deck is None else deck.force_study()
    
@study_bp.route("/casualmode/<int:deck_id>")
@login_required
@log_decorator
def casual_mode(deck_id):
    return render_template("study_bp/casualmode.html", title="Casual Mode", deck=deck_id)   