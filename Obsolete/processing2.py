from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, CONST_PLAN
from datetime import datetime, timedelta
import json
from flask import current_app
from random import randrange
from time import sleep
from cardcreator import creator, create_image, split_text
from extractors import summarize, turn_to_notes, add_period, extract_from_pdf, large_extract_terms, extract_from_pptx, extract_terms, extract_from_docx, extract_audio, transcribe_and_translate
from app import app
from models import db, Job, TestResult, QuestionResult, Question, Test, Feedback, ResponseData, DeckFiles, Subscriber, Deck, SharedDecks, Card
from models import UsageRecord, SubscriptionPlan, User, cards, source_files, cards_shared, questions, distribution
import asyncio
import aiohttp
from aiohttp import ClientSession
from sqlalchemy.orm import object_session



async def process_jobs():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    while True:
        with session_factory() as session:
            print("Checking for jobs...")
            slug = await find_pending_job(session)
            if slug:
                retries = 0
                while retries < 3:
                    try:
                        print(retries)
                        await process_job(slug, session)
                        break
                    except Exception as e:
                        retries += 1
                        print(f"Error: {e}. Retrying ({retries}/3)")
                        if retries == 3:
                            print("Job failed, moving on.")
                            slug.state = "completed"
                            slug.error_type = "error"
                            db.session.commit()
                            break
            else:
                print("No jobs found.")
                await asyncio.sleep(1)

async def find_pending_job(session):
    with current_app.app_context():
        try:
            queue = db.session.query(Job).filter_by(state="queued")
            if job := queue.first():
                job.state = "processing"
                print("found job", job)
                db.session.commit()
                merged_job = db.session.merge(job)  # Merge the job object back to the session
                return merged_job
        except Exception as e:
            print(f"Error while finding pending job: {e}")
            db.session.rollback()
            return None
        
async def process_job(slug, session):
    
    with current_app.app_context():
        slug = db.session.merge(slug)  # Merge the slug object back to the session
        session = db.session.object_session(slug)
        if session is None:
            print("Object is not bound to a session.2", slug)
        elif session:
            print("Object is bound to a session.2", slug)
        try:
            method = None
            print(f"Processing job: {slug}...", end=" ", flush=True)
            payload = json.loads(slug.payload)
            deck_id = payload["deck"]
            deck = Deck.query.filter_by(id=deck_id).first()
            if deck == None:
                print("deck is none, deleting job")
                db.session.delete(slug)
                db.session.commit()
                return
            deck = session.merge(deck)
            text = payload["text"]
            prompt_options = payload["prompt_options"]
            main_opt = prompt_options['main_opt']
            print(main_opt)
            trans_opt = prompt_options['trans_opt']
            long_form = ["Transcribe", "Turn2notes", "Summarize"]
            if main_opt not in long_form:
                print("not in long form")
                method = "extract"
                try:
                    response = await extract_terms(text, prompt_options)
                    print("OPEN AI RESPONSE RETURNED TO PROCESSING PRINTING RESPONSE")
                    print(response[0])
                    save_terms_to_deck(deck, response[0], prompt_options, method)
                    print(response[2])
                except Exception as e:
                    print(f"Error: {e}.")
                try:
                    log_response_data(response[1], response[2], response[3], True)
                except Exception as e:
                    print(f"Error: {e}.")
                print("NOT TRANSCRIBE DONE")
            elif main_opt  == "Transcribe":
                method = "Transcription"
                print("main option is transcribe")
                if trans_opt != None:
                    if trans_opt != "":

                        processed_text = transcribe_and_translate(text, prompt_options)
            elif main_opt == "Turn2notes":
                method = "Notes"
                print(text, prompt_options)
                processed_text = turn_to_notes(text, prompt_options)
            elif main_opt == "Summarize":
                method = "Summary"
                print(text, prompt_options)
                processed_text = summarize(text, prompt_options)

            if main_opt in long_form:
                print("about to save source text")
                try:
                    save_source_text_to_deck(slug.slug, deck, processed_text, prompt_options, method)

                    if slug.item_number == slug.item_quantity:
                        files = DeckFiles.query.filter_by(file_name=slug.slug).all()
                        now = datetime.utcnow().isoformat()
                        name = str(deck_id) + now
                        final_string = ""
                        for file in files:
                            final_string = final_string + file.text_string
                        file_storage = DeckFiles(file_name=name, text_string=final_string, create_type = method, time_created = datetime.utcnow())
                        db.session.add(file_storage)
                        deck.deck_files.append(file_storage)
                        for file in files:
                            db.session.delete(file)
                        db.session.commit()
                except Exception as e:
                    print(f"Error while saving source text to deck: {e}")
                    db.session.rollback()


            if prompt_options['save_text_opt'] == True:
                method = "Source"
                save_source_text_to_deck(slug.slug, deck, text, prompt_options, method)

            if check_subscription_plan(slug.user) == CONST_PLAN:
                if prompt_options['images_opt'] == True:
                    generate_images(deck)

            # The heavy processing happens here:
            # I use a short wait time here to ease development,
            # but you can experiment with time > 5 min
            # and see if the web app will manage it!
            print(" JUST BEFORE CHANGE OF STATE ")
            with current_app.app_context():
                merged_slug = db.session.merge(slug)

                merged_slug.state = "completed"
                db.session.add(merged_slug)
                db.session.commit()

                print(slug.state)
                jobs = Job.query.filter_by(slug=slug.slug).all()
                counter = 0
                for job in jobs:
                    if job.state == "completed":
                        counter = counter + 1
                        if counter == len(jobs):
                            for job in jobs:
                                job.result = 1
                            print("all jobs completed")
            
                db.session.commit()
        except Exception as e:
            print(" ERROR IN PROCESSING JOB")
            print(f"Error: {e}")
            db.session.rollback()




def log_response_data(prompt, response, content, success):
    prompt_json = json.dumps(prompt)
    response_json = json.dumps(response)
    content_json = json.dumps(content)
    response_log = ResponseData(prompt=prompt_json, response=response_json, content=content_json, success=success)
    db.session.add(response_log)
    db.session.commit()

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
    try:
        if isinstance(terms, dict):
            terms = [terms]
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
                print(item)
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
    except Exception as e:
        print(f"Error while saving terms to deck: {e}")
        db.session.rollback()


def generate_images(deck):
    for card in deck.cards:
        if card.img == None:
            try:
                card.img = create_image(card.term)
                db.session.commit()
            except:
                pass
    return True


def save_source_text_to_deck(name, deck, text, prompt_options, method="extract"):
    print("entered save_source_text_to_deck", deck, text, prompt_options, method)
    main_opt = prompt_options['main_opt']
    f_name = name
    file_storage = DeckFiles(file_name=f_name, text_string=text, create_type = "source", time_created = datetime.utcnow())
    db.session.add(file_storage)
    deck.deck_files.append(file_storage)
    try:
        db.session.commit()
    except Exception as e:
        print(f"Error while saving source text to deck: {e}")
        db.session.rollback()
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
        async def main():
            num_workers = 5  # Number of concurrent workers to run
            tasks = []
            for i in range(num_workers):
                task = asyncio.create_task(process_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())