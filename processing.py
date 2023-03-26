from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, CONST_PLAN
from datetime import datetime, timedelta
import json
from flask import current_app

from random import randrange
from time import sleep

from cardcreator import creator, create_image

from extractors import add_period
from app import app
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution

engine = create_engine(
    SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS
)
print(engine)


def find_pending_job():
    with current_app.app_context():
        queue = Session.query(Job).filter_by(state="queued")
        if job := queue.first():
            job.state = "processing"
            return job




def process_job(slug):
    print(f"Processing job: {slug}...", end=" ", flush=True)
    print(slug)
    payload = json.loads(slug.payload)
    
    deck_id = payload["deck"]
    deck = Deck.query.filter_by(id=deck_id).first()
    text = payload["text"]
    prompt_options = payload["prompt_options"]
    terms = creator(text, prompt_options)[0]
    save_terms_to_deck(deck, terms, prompt_options)
    if prompt_options['main_opt'] == "Transcribe" or prompt_options['save_text_opt'] == True:
        save_source_text_to_deck(deck, text, prompt_options)
    if check_subscription_plan(slug.user) == CONST_PLAN:
        if prompt_options['images_opt'] == True:
            generate_images(deck)

    # The heavy processing happens here:
    # I use a short wait time here to ease development,
    # but you can experiment with time > 5 min
    # and see if the web app will manage it!
    
    with current_app.app_context():
        job = Job.query.filter_by(slug=slug.slug).first()
        job.state = "completed"
        job.result = 1
        print(slug.state)
        print(db.session.dirty)
        db.session.commit()
        

    print(f"{slug.slug} finished processing!")



def save_terms_to_deck(deck, terms, prompt_options, method="extract"):
    mapping = {
    "Definitions": ("A", "B"),
    "Translate": ("A", "B"),
    "Rhyme": ("A", "B"),
    "People": ("A", "B"),
    "Theories": ("A", "B"),
    "Cloze": ("A", "B"),
    "Mcq": ("A", "B", "C", "D", "E"),
    "Comprehension": ("A", "B"),
    "Vocab_builder": ("A", "B"),
    "Formulas": ("A", "B", "C"),
    }
    main_opt = prompt_options['main_opt']
    trans_opt = prompt_options['trans_opt']
    cat = main_opt
    if main_opt == "Mcq":
        v, w, x, y, z = mapping.get(main_opt, ("A", "B", "C", "D", "E"))
        for item in terms:
            term = item[v].capitalize()
            if check_card_exist(deck, term) == False:
                entry = Card(category = cat, term=term, content=(add_period(item[w].capitalize())), boc_2=(add_period(item[x].capitalize())), boc_3=(add_period(item[y].capitalize())), boc_4=(add_period(item[z].capitalize())), create_method = method)
                db.session.add(entry)
                deck.cards.append(entry)
                db.session.commit()
    elif main_opt != "Mcq" and main_opt != "Transcribe" and main_opt != "Formulas":
        x, y = mapping.get(main_opt, ("A", "B"))
        for item in terms:
            term=item[x].capitalize()
            if check_card_exist(deck, term) == False:
                entry = Card(category = cat, term=term, content=add_period(item[y].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
        db.session.commit()
    elif main_opt == "Formulas":
        x, y, z = mapping.get(main_opt, ("A", "B", "C"))
        for item in terms:
            term=item[x].capitalize()
            if check_card_exist(deck, term) == False:
                entry = Card(category = cat, term=term, formula="\["+(item[y])+"\]", content=add_period(item[z].capitalize()), create_method=method)
                db.session.add(entry)
                deck.cards.append(entry)
        db.session.commit()
    elif main_opt == "Transcribe":
        if trans_opt != None:
            name = deck.name + "_" + method + "_" + main_opt + trans_opt + "_" + str(datetime.utcnow())
            create_type = trans_opt + " translation"
            transcript_trans = DeckFiles(file_name = name, text_string = terms, time_created = datetime.utcnow(), create_type = create_type)
            db.session.add(transcript_trans)
            deck.deck_files.append(transcript_trans)
            db.session.commit()
            return print(f"Transcription {transcript_trans.file_name} created")
    return True


def generate_images(deck):
    for card in deck.cards:
        if card.img == None:
            try:
                card.img = create_image(card.term)
                db.session.commit()
            except:
                pass
    return True


def save_source_text_to_deck(deck, text, prompt_options, method="extract"):
    main_opt = prompt_options['main_opt']
    f_name = deck.name + "_" + method + "_" + main_opt + "_" + str(datetime.utcnow())
    file_storage = DeckFiles(file_name=f_name, text_string=text, create_type = "source", time_created = datetime.utcnow())
    db.session.add(file_storage) 
    deck.deck_files.append(file_storage)
    db.session.commit() 
    return True



def check_card_exist(deck, term):
    deck = Deck.query.filter_by(id=deck.id).first()
    for card in deck.cards:
        if card.term == term:
            print("card {} already exists".format(term))
            return True
    else:
        return False

def check_subscription_plan(user_id):
    user = User.query.filter_by(id=user_id).first()
    subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
    return subscription_plan




if __name__ == "__main__":
    with app.app_context():
        while True:
            Session = scoped_session(sessionmaker(bind=engine))

            print("Checking for jobs...")
            slug = find_pending_job()
            if slug:
                print("processing", slug)
                process_job(slug)
            else:
                Session.commit()
                Session.remove() 
                # We don't need to continuously hammer the database
                # if there are no requests coming in, so let's
                # give it a break!
                sleep(1)