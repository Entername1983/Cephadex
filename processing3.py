from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, CONST_PLAN
from datetime import datetime, timedelta
import json
from flask import current_app
from random import randrange
from time import sleep
from cardcreator import creator, split_text
from extractors import create_image, summarize, turn_to_notes, add_period, extract_from_pdf, large_extract_terms, extract_from_pptx, extract_terms, extract_from_docx, extract_audio, transcribe_and_translate
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
from datetime import timezone

async def process_jobs():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    process_job_functions = {
        "audio": process_audio_job,
        "default": process_job,
    }
    while True:
        with session_factory() as session:
            if slug := select_pending_job(session):
                process_function = process_job_functions.get(slug.task_type,
                 process_job_functions["default"])
                await process_with_retry(slug, session, process_function)
            else:
                await asyncio.sleep(1)

def select_pending_job(session):
    functions = [find_pending_job, find_pending_audio_job]
    selected_function = random.choice(functions)
    return selected_function(session)

async def process_with_retry(slug, session, process_function):
    MAX_RETRIES = 3
    for retry in range(MAX_RETRIES):
        try:
            print(retry)
            await process_function(slug, session)
            break
        except Exception as e:
            print(f"Error: {e}. Retrying ({retry + 1}/{MAX_RETRIES})")
            if retry == MAX_RETRIES - 1:
                handle_job_failure_1(slug, session)
                print("Job failed, moving on.")

def handle_job_failure_1(slug, session):
    slug.state = "completed" if slug.task_type != "audio" else "finished"
    slug.error_type = "error"
    session.commit()





async def find_pending_audio_job(session):
    with current_app.app_context():
        try:
            queue = session.query(Job).filter_by(state="pending", task_type="audio")
            if job := queue.first():
                job.state = "processing"
                print("found job", job)
                session.commit()
                return session.merge(job) 
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
                return session.merge(job)
        except Exception as e:
            print(f"Error while finding pending job: {e}")
            session.rollback()
            return None


##### PROCESS AUDIO JOB FUNCTIONS #####
async def process_audio_job(slug, session):
    retries = 3
    retry_delay = 1  # Delay in seconds between retries

    for attempt in range(retries):
        try:
            await process_single_audio_job(slug, session)
            break
        except Exception as e:
            print(f"Error in processing audio job: {e}")
            if attempt < retries - 1:
                print("Retrying audio job after delay...")
                await asyncio.sleep(retry_delay)
            else:
                print("Audio job processing failed after multiple retries.")

async def process_single_audio_job(slug, session):
    with current_app.app_context():
        slug, payload, task_type, segment, user_id, deck_id = setup_audio_job(slug, session)
        text = await transcribe_and_delete_file(segment)
        finalize_audio_job(slug, session, deck_id, text, payload, task_type, user_id)

def setup_audio_job(slug, session):
    slug = session.merge(slug)
    session = session.object_session(slug)
    payload = json.loads(slug.payload)
    prompt_options = payload["prompt_options"]
    task_type = prompt_options['main_opt']
    segment = payload["segment"]
    user_id = payload["user_id"]
    deck_id = slug.deck_id

    return slug, payload, task_type, segment, user_id, deck_id

async def transcribe_and_delete_file(segment):
    text = await transcribe_whisper(segment)
    try:
        os.remove(segment)
        print(f"File '{segment}' has been successfully deleted.")
    except OSError as e:
        print(f"Error occurred while deleting the file '{segment}': {str(e)}")
    return text

def finalize_audio_job(slug, session, deck_id, text, payload, task_type, user_id):
    new_payload = {'deck': deck_id, 'text': text, 'prompt_options': payload["prompt_options"]}
    new_job = Job(slug=slug.slug, user=user_id, task_type=task_type,
                  payload=json.dumps(new_payload), state="queued",
                  item_number=slug.item_number, item_quantity=slug.item_quantity,
                  deck_id=deck_id, processed_content=text)
    slug.state = "completed"
    slug.processed_content = text
    slug.save_source = True
    session.add(new_job)
    session.commit()


##### PROCESS JOB FUNCTIONS #####
async def process_job(slug, session):
    retries = 3
    retry_delay = 1
    for attempt in range(retries):
        try:
            result = await process_single_job(slug, session)
            if result:
                break
        except Exception as e:
            print(f"Error in processing job: {e}")
            if attempt < retries - 1:
                print("Retrying job after delay...")
                await asyncio.sleep(retry_delay)
            else:
                handle_job_failure_2(slug, session)

async def process_single_job(slug, session):
    with current_app.app_context():
        merged_slug, deck, payload, main_opt, trans_opt = setup_job(slug, session)
        if main_opt not in ["Transcribe", "Turn2notes", "Summarize"]:
            handle_extract_terms(merged_slug, deck, payload, session)
        else:
            await handle_long_form(merged_slug, main_opt, trans_opt, payload)
        if check_subscription_plan(merged_slug.user) == CONST_PLAN and payload['prompt_options']['images_opt']:
            await generate_images(deck, session)

        finalize_job(merged_slug, session)

def setup_job(slug, session):
    merged_slug = session.merge(slug)
    payload = json.loads(merged_slug.payload)
    deck_id = payload["deck"]
    deck = Deck.query.filter_by(id=deck_id).first()
    if deck is None:
        print("Deck is None, deleting job")
        session.delete(merged_slug)
        session.commit()
        return
    deck = session.merge(deck)
    main_opt = payload["prompt_options"]['main_opt']
    trans_opt = payload["prompt_options"]['trans_opt']
    return merged_slug, deck, payload, main_opt, trans_opt

def handle_extract_terms(merged_slug, deck, payload, session):
    try:
        method = "extract"
        response = asyncio.run(extract_terms(payload["text"], payload["prompt_options"]))
        process_response(response, merged_slug)
        save_terms_to_deck(deck, response[0], payload["prompt_options"], method, session)
    except Exception as e:
        print(f"Error in extract_terms: {e}.")
        merged_slug.processed_content = "Error"
        session.commit()

def process_response(response, merged_slug):
    if isinstance(response[0], list):
        merged_slug.processed_content = ", ".join([str(item) for item in response[0]])
    elif isinstance(response[0], dict):
        merged_slug.processed_content = str(response[0])
    else:
        merged_slug.processed_content = response[0]
    print(f"OpenAI response returned to processing. Printing response: {response[0]}")

async def handle_long_form(merged_slug, main_opt, trans_opt, payload):
    method = None
    processed_text = None
    if main_opt == "Transcribe":
        method = "Transcription"
        if trans_opt:
            processed_text = await transcribe_and_translate(payload["text"], payload["prompt_options"])
    elif main_opt == "Turn2notes":
        method = "Notes"
        processed_text = await turn_to_notes(payload["text"], payload["prompt_options"])
    elif main_opt == "Summarize":
        method = "Summary"
        processed_text = await summarize(payload["text"], payload["prompt_options"])
    if processed_text:
        merged_slug.processed_content = processed_text

def finalize_job(merged_slug, session):
    with current_app.app_context():
        merged_slug.state = "completed"
        session.add(merged_slug)
        session.commit()
        print("State of slug: ", merged_slug.state)
        jobs = Job.query.filter_by(slug=merged_slug.slug).all()
        if all(job.state == "completed" for job in jobs):
            for job in jobs:
                job.result = 1
            print("All jobs completed")
        session.commit()

def handle_job_failure_2(slug, session):
    with current_app.app_context():
        merged_slug = session.merge(slug)
        merged_slug.state = "failed"
        session.add(merged_slug)
        session.commit()
    print("Job processing failed after multiple retries.")



def log_response_data(prompt, response, content, success, session=None):
    prompt_json = json.dumps(prompt)
    response_json = json.dumps(response)
    content_json = json.dumps(content)
    response_log = ResponseData(prompt=prompt_json,
                            response=response_json, content=content_json, success=success)
    session.add(response_log)
    session.commit()



##### SAVING TERMS TO DECK FUNCTIONS ######
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

def process_terms(item, keys):
    results = []
    for key in keys:
        result = item.get(key)
        result = ' '.join(result) if isinstance(result, list) else result
        result = add_period(result.capitalize()) if result else None
        results.append(result)
    return results

def process_mcq_terms(session, deck, terms, cat, method):
    for item in terms:
        term, content, boc_2, boc_3, boc_4 = process_terms(item, mapping["Mcq"])
        if term and not check_card_exist(deck, term):
            entry = Card(
                category=cat,
                term=term,
                content=content,
                boc_2=boc_2,
                boc_3=boc_3,
                boc_4=boc_4,
                create_method=method)
            session.add(entry)
            deck.cards.append(entry)
            session.commit()

def process_default_terms(session, deck, terms, cat, method):
    for item in terms:
        term, content = process_terms(item, mapping[cat])
        if term and not check_card_exist(deck, term):
            entry = Card(category=cat, term=term, content=content, create_method=method)
            session.add(entry)
            deck.cards.append(entry)
            session.commit()

def process_formula_terms(session, deck, terms, cat, method):
    for item in terms:
        term, formula, content = process_terms(item, mapping[cat])
        formula = "\[" + formula + "\]" if formula else None
        if term and not check_card_exist(deck, term):
            entry = Card(category=cat, term=term, formula=formula, content=content, create_method=method)
            session.add(entry)
            deck.cards.append(entry)
            session.commit()

def process_transcribe_terms(session, deck, terms, prompt_options, method):
    trans_opt = prompt_options['trans_opt']
    if trans_opt is not None:
        name = f"{deck.name}_{method}_Transcribe{trans_opt}_{str(datetime.now(timezone.utc))}"
        create_type = f"{trans_opt} translation"
        transcript_trans = DeckFiles(file_name = name, text_string = terms,
                            time_created=datetime.now(timezone.utc),
                            create_type = create_type)
        session.add(transcript_trans)
        deck.deck_files.append(transcript_trans)
        session.commit()
        print(f"Transcription {transcript_trans.file_name} created")

def save_terms_to_deck(deck, terms, prompt_options, method="extract", session=None):
    if isinstance(terms, dict):
        terms = [terms]

    main_opt = prompt_options['main_opt']
    cat = main_opt

    try:
        if main_opt == "Mcq":
            process_mcq_terms(session, deck, terms, cat, method)
        elif main_opt not in ['Mcq', 'Transcribe', 'Formulas', 'turn2notes', 'summarize']:
            process_default_terms(session, deck, terms, cat, method)
        elif main_opt == "Formulas":
            process_formula_terms(session, deck, terms, cat, method)
        elif main_opt == "Transcribe":
            process_transcribe_terms(session, deck, terms, prompt_options, method)
        return True
    except Exception as e:
        print(f"Error while saving terms to deck: {e}")
        session.rollback()
        raise



def generate_images(deck, session=None):
    for card in deck.cards:
        if card.img is None:
            try:
                card.img = create_image(card.term)
                session.commit()
            except Exception as e:
                raise e
    return True





def check_card_exist(deck, term):
    deck = Deck.query.filter_by(id=deck.id).first()
    for card in deck.cards:
        if card.term == term:
            print(f"card {term} already exists")
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
            for _ in range(num_workers):
                task = asyncio.create_task(process_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())





async def process_job(slug, session):
    retries = 3
    retry_delay = 1  # Delay in seconds between retries
    retry_counter = 0
    while retry_counter < retries:
        try:
            result = await process_single_job(slug, session)
            if result:
                break
            with current_app.app_context():
                slug = session.merge(slug)  # Merge the slug object back to the session
                session = session.object_session(slug)

                method = None
                print(f"Processing job: {slug}...", end=" ", flush=True)
                payload = json.loads(slug.payload)
                deck_id = payload["deck"]
                deck = Deck.query.filter_by(id=deck_id).first()
                if deck is None:
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
                        slug.processed_content = "Error"
                        session.commit()
                    try:
                        log_response_data(response[1], response[2], response[3], True, session)
                    except Exception as e:
                        print(f"Error: {e}.")
                    print("NOT TRANSCRIBE DONE")
                    print("main option", main_opt)
                elif main_opt  == "Transcribe":
                    method = "Transcription"
                    print("main option is transcribe")
                    if trans_opt not in [None, ""]:
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

                if prompt_options['images_opt'] == True:
                    if check_subscription_plan(slug.user) in CONST_PLAN:
                        await generate_images(deck, session)

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