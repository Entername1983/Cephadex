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
import random
from extractors import transcribe_whisper
import os

async def process_jobs():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    while True:
        with session_factory() as session:
            functions = [find_pending_job, find_pending_audio_job]
            selected_function = random.choice(functions)
            slug = await selected_function(session)

            if slug:
                if slug.task_type == "audio" and slug.state == "processing":
                    print("recognized job as audio and processing")
                    retries = 0
                    while retries < 3:
                        try:
                            print(retries)
                            await process_audio_job(slug, session)
                            break
                        except Exception as e:
                            retries += 1
                            print(f"Error: {e}. Retrying ({retries}/3)")
                            if retries == 3:
                                print("Job failed, moving on.")
                                slug.state = "finished"
                                slug.error_type = "error"
                                session.commit()
                                break
                else:
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
                                session.commit()
                                break
            else:
                await asyncio.sleep(1)

async def find_pending_audio_job(session):
    with current_app.app_context():
        try:
            queue = session.query(Job).filter_by(state="pending", task_type="audio")
            if job := queue.first():
                job.state = "processing"
                print("found job", job)
                session.commit()
                merged_job = session.merge(job)  # Merge the job object back to the session
                return merged_job
        except Exception as e:
            print(f"Error while finding pending job: {e}")
            session.rollback()
            return None

async def find_pending_job(session):
    with current_app.app_context():
        try:
            queue = session.query(Job).filter_by(state="queued")
            if job := queue.first():
                job.state = "processing"
                print("found job", job)
                session.commit()
                merged_job = session.merge(job)  # Merge the job object back to the session
                return merged_job
        except Exception as e:
            print(f"Error while finding pending job: {e}")
            session.rollback()
            return None
async def process_audio_job(slug, session):
    print("Processing audio job...")
    retries = 3
    retry_delay = 1  # Delay in seconds between retries
    retry_counter = 0

    while retry_counter < retries:
        try:
            with current_app.app_context():
                slug = session.merge(slug)  # Merge the slug object back to the session
                session = session.object_session(slug)
                if session is None:
                    print("Object is not bound to a session.2", slug)
                elif session:
                    print("Object is bound to a session.2", slug)
                payload = json.loads(slug.payload)
                prompt_options = payload["prompt_options"]
                task_type = prompt_options['main_opt']
                segment = payload["segment"]
                user_id = payload["user_id"]
                deck_id = slug.deck_id
                
                text = await transcribe_whisper(segment)
                try:
                    os.remove(segment)
                    print(f"File '{segment}' has been successfully deleted.")
                except OSError as e:
                    print(f"Error occurred while deleting the file '{segment}': {str(e)}")
                new_payload = {'deck': deck_id, 'text': text,
                                'prompt_options': prompt_options}
                new_job = Job(slug=slug.slug, user = user_id, task_type=task_type,
                    payload = json.dumps(new_payload), state="queued",
                    item_number = slug.item_number, item_quantity = slug.item_quantity,
                    deck_id = deck_id, processed_content = text
                )
                slug.state = "completed"
                slug.processed_content = text
                slug.save_source = True
                session.add(new_job)
                session.commit()
                break
        except Exception as e:
            print(" ERROR IN PROCESSING AUDIO JOB")
            print(f"Error: {e}")
            session.rollback()
            retry_counter += 1
            
            if retry_counter < retries:
                print("Retrying audio job after delay...")
                await asyncio.sleep(retry_delay)  # Wait for the specified delay before retrying


async def process_job(slug, session):
    retries = 3
    retry_delay = 1  # Delay in seconds between retries
    retry_counter = 0

    while retry_counter < retries:
        try:
            with current_app.app_context():
                slug = session.merge(slug)  # Merge the slug object back to the session
                session = session.object_session(slug)
                if session is None:
                    print("Object is not bound to a session.2", slug)
                elif session:
                    print("Object is bound to a session.2", slug)
                
                method = None
                print(f"Processing job: {slug}...", end=" ", flush=True)
                payload = json.loads(slug.payload)
                deck_id = payload["deck"]
                deck = Deck.query.filter_by(id=deck_id).first()
                if deck == None:
                    print("deck is none, deleting job")
                    session.delete(slug)
                    session.commit()
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
                        if isinstance(response[0], list):
                            slug.processed_content = ", ".join([str(item) for item in response[0]])
                        elif isinstance(response[0], dict):
                            slug.processed_content = str(response[0])
                        else:
                            slug.processed_content = response[0]
                        print("OPEN AI RESPONSE RETURNED TO PROCESSING PRINTING RESPONSE")
                        print(response[0])
                        save_terms_to_deck(deck, response[0], prompt_options, method, session)
                        print(response[2])
                    except Exception as e:
                        print(f"Error: {e}.")
                    try:
                        log_response_data(response[1], response[2], response[3], True, session)
                    except Exception as e:
                        print(f"Error: {e}.")
                    print("NOT TRANSCRIBE DONE")
                    print("main option", main_opt)
                elif main_opt  == "Transcribe":
                    method = "Transcription"
                    print("main option is transcribe")
                    if trans_opt != None:
                        if trans_opt != "":
                            processed_text = await transcribe_and_translate(text, prompt_options)
                            slug.processed_content=processed_text

                elif main_opt == "Turn2notes":
                    method = "Notes"
                    print(text, prompt_options)
                    processed_text = await turn_to_notes(text, prompt_options)
                    slug.processed_content=processed_text

                elif main_opt == "Summarize":
                    method = "Summary"
                    print("Calling summarize with:", text, prompt_options)
                    processed_text = await summarize(text, prompt_options)
                    print("Processed text from summarize:", processed_text)
                    slug.processed_content=processed_text

                if check_subscription_plan(slug.user) == CONST_PLAN:
                    if prompt_options['images_opt'] == True:
                        generate_images(deck, session)

                print(" JUST BEFORE CHANGE OF STATE ")
                with current_app.app_context():
                    merged_slug = session.merge(slug)

                    merged_slug.state = "completed"
                    session.add(merged_slug)
                    session.commit()
                    ## code below is likely obsolete, double check
                    print("state of slug: ", merged_slug.state)
                    jobs = Job.query.filter_by(slug=merged_slug.slug).all()
                    counter = 0
                    for job in jobs:
                        print("entered job in jobs loop")
                        print("job state: ", job.state)
                        if job.state == "completed":
                            print("recognized job as completed")
                            counter = counter + 1
                            if counter == len(jobs):
                                for job in jobs:
                                    job.result = 1
                                print("all jobs completed")
                
                    session.commit()
                    break
        except Exception as e:
            print(" ERROR IN PROCESSING JOB")
            print(f"Error: {e}")
            session.rollback()
            retry_counter += 1
            
            if retry_counter < retries:
                print("Retrying job after delay...")
                await asyncio.sleep(retry_delay)  # Wait for the specified delay before retrying

    if retry_counter == retries:
        print("Job processing failed after multiple retries.")
        with current_app.app_context():
            slug = session.merge(slug)
            slug.state = "failed"
            session.add(slug)
            session.commit()



def log_response_data(prompt, response, content, success, session=None):
    prompt_json = json.dumps(prompt)
    response_json = json.dumps(response)
    content_json = json.dumps(content)
    response_log = ResponseData(prompt=prompt_json,
                            response=response_json, content=content_json, success=success)
    session.add(response_log)
    session.commit()

def save_terms_to_deck(deck, terms, prompt_options, method="extract", session=None):
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
                    entry = Card(category = cat,
                        term=term, content=(add_period(item[w].capitalize())),
                        boc_2=(add_period(item[x].capitalize())), 
                        boc_3=(add_period(item[y].capitalize())), 
                        boc_4=(add_period(item[z].capitalize())), create_method = method)
                    session.add(entry)
                    deck.cards.append(entry)
                    session.commit()
        elif main_opt != "Mcq" and main_opt != "Transcribe" and main_opt != "Formulas":
            x, y = mapping.get(main_opt, ("A", "B"))
            for item in terms:
                print(item)
                term=item[x].capitalize()
                if check_card_exist(deck, term) == False:
                    entry = Card(category = cat, term=term,
                        content=add_period(item[y].capitalize()), create_method=method)
                    session.add(entry)
                    deck.cards.append(entry)
            session.commit()
        elif main_opt == "Formulas":
            x, y, z = mapping.get(main_opt, ("A", "B", "C"))
            for item in terms:
                term=item[x].capitalize()
                if check_card_exist(deck, term) == False:
                    entry = Card(category = cat, term=term, formula="\["+(item[y])+"\]",
                        content=add_period(item[z].capitalize()), create_method=method)
                    session.add(entry)
                    deck.cards.append(entry)
            session.commit()
        elif main_opt == "Transcribe":
            if trans_opt != None:
                name = deck.name + "_" + method + "_" + main_opt + trans_opt + "_" + str(datetime.utcnow())
                create_type = trans_opt + " translation"
                transcript_trans = DeckFiles(file_name = name, text_string = terms,
                                    time_created = datetime.utcnow(),
                                    create_type = create_type)
                session.add(transcript_trans)
                deck.deck_files.append(transcript_trans)
                session.commit()
                return print(f"Transcription {transcript_trans.file_name} created")
        return True
    except Exception as e:
        print(f"Error while saving terms to deck: {e}")
        session.rollback()


def generate_images(deck, session=None):
    for card in deck.cards:
        if card.img == None:
            try:
                card.img = create_image(card.term)
                session.commit()
            except:
                pass
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
            num_workers = 30  # Number of concurrent workers to run
            tasks = []
            for i in range(num_workers):
                task = asyncio.create_task(process_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())