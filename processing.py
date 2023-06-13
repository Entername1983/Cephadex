from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime
import json
from flask import current_app
from extractors import create_image, summarize, turn_to_notes, add_period, extract_terms
from extractors import transcribe_and_translate
from app import app
from models import Job, ResponseData, DeckFiles, Deck, Card
from models import SubscriptionPlan, User
import asyncio
import random
from extractors import transcribe_whisper
import os
from datetime import timezone

SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
SQLALCHEMY_ENGINE_OPTIONS = json.loads(os.environ['SQLALCHEMY_ENGINE_OPTIONS'])
CONST_PLAN = os.environ.get("CONST_PLAN")
NUM_WORKERS_PROCESSOR = os.environ.get("NUM_WORKERS_PROCESSOR")
SLEEP_TIME = int(os.environ.get("SLEEP_TIME"))


async def process_jobs():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    while True:
        with session_factory() as session:
            functions = [find_pending_job, find_pending_audio_job]
            selected_function = random.choice(functions)
            slug = await selected_function(session)

            if slug:
                retries = 0
                if slug.task_type == "audio" and slug.state == "processing":
                    print("recognized job as audio and processing")
                    
                    while retries < 3:
                        try:
                            await process_audio_job(slug, session)
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
                    while retries < 3:
                        try:
                            print(retries)
                            await process_single_job(slug, session)
                            slug.state = "completed"
                            session.commit()
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
                await asyncio.sleep(SLEEP_TIME)



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
            print(f"ERROR IN PROCESSING AUDIO JOB Error: {e}")
            session.rollback()
            retry_counter += 1
            
            if retry_counter < retries:
                print("Retrying audio job after delay...")
                await asyncio.sleep(retry_delay) 


async def process_single_job(slug, session):
    with current_app.app_context():
        merged_slug, deck, payload, main_opt, trans_opt = setup_job(slug, session)
        if main_opt not in ["Transcribe", "Turn2notes", "Summarize"]:
            await handle_extract_terms(merged_slug, deck, payload, session)
        else:
            await handle_long_form(merged_slug, main_opt, trans_opt, payload)
        if check_subscription_plan(merged_slug.user) == CONST_PLAN and payload['prompt_options']['images_opt']:
            await generate_images(deck, session)

      #### finalize_job(merged_slug, session)



async def handle_extract_terms(merged_slug, deck, payload, session):
    method = "extract"
    response = await(extract_terms(payload["text"], payload["prompt_options"]))
    process_response(response, merged_slug)
    counter = save_terms_to_deck(deck, response[0], payload["prompt_options"],
            method, session)
    merged_slug.qty_cards_created = counter

def process_response(response, merged_slug):
    if isinstance(response[0], list):
        merged_slug.processed_content = ", ".join([str(item) for item in response[0]])
    elif isinstance(response[0], dict):
        merged_slug.processed_content = str(response[0])
    else:
        merged_slug.processed_content = response[0]
    if merged_slug.processed_content == "":
        raise ValueError("Processed content is empty.")
    message = (f"OpenAI response returned to processing. Printing response: {merged_slug.processed_content}")
    print(message[:100])

async def handle_long_form(merged_slug, main_opt, trans_opt, payload):
    print("Handling long form...")
    method = None
    processed_text = None
    if main_opt == "Transcribe":
        method = "Transcription"
        if trans_opt:
            processed_text = await transcribe_and_translate(payload["text"],
             payload["prompt_options"])
    elif main_opt == "Turn2notes":
        method = "Notes"
        processed_text = await turn_to_notes(payload["text"], payload["prompt_options"])
    elif main_opt == "Summarize":
        method = "Summary"
        processed_text = await summarize(payload["text"], payload["prompt_options"])

    if processed_text:
        merged_slug.processed_content = processed_text
    if merged_slug.processed_content == "":
        raise ValueError("Processed content is empty.")






##### SAVE TERMS TO DECK ####
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
    "Explain": ("A", "B"),
    "Discuss": ("A", "B"),
    }

def save_terms_to_deck(deck, terms, prompt_options, method="extract", session=None):
    main_opt = prompt_options['main_opt']
    trans_opt = prompt_options['trans_opt']
    cat = main_opt
    try:
        print(f"Saving terms to deck: {terms}")
    except Exception:
        pass
    try:
        if isinstance(terms, dict):
            terms = [terms]
        if main_opt == "Mcq":
            counter = process_mcq_terms(session, deck, terms, cat, method, main_opt)
        elif main_opt not in ['Mcq', 'Transcribe', 'Formulas', 'turn2notes', 'summarize', 'Discuss']:
            counter = process_default_terms(session, deck, terms, cat, method, main_opt)
        elif main_opt == "Formulas":
           counter = process_formula_terms(session, deck, terms, cat, method, main_opt)
        elif main_opt == "Discuss":
           counter = process_discuss_terms(session, deck, terms, cat, method, main_opt)
        elif main_opt == "Transcribe":
            counter = process_translation(session, deck, terms, prompt_options, method, main_opt, trans_opt)
        return counter
    
    except Exception as e:
        print(f"Error while saving terms to deck: {e}")
        session.rollback()

def process_mcq_terms(session, deck, terms, cat, method, main_opt):
    v, w, x, y, z = mapping.get(main_opt, ("A", "B", "C", "D", "E"))
    counter = 0
    for item in terms:
        try:
            term = item.get(v)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            content = item.get(w)
            content = ' '.join(content) if isinstance(content, list) else content
            content = add_period(content) if content else None
            boc_2 = item.get(x)
            boc_2 = ' '.join(boc_2) if isinstance(boc_2, list) else boc_2
            boc_2 = add_period(boc_2) if boc_2 else None
            boc_3 = item.get(y)
            boc_3 = ' '.join(boc_3) if isinstance(boc_3, list) else boc_3
            boc_3 = add_period(boc_3) if boc_3 else None
            boc_4 = item.get(z)
            boc_4 = ' '.join(boc_4) if isinstance(boc_4, list) else boc_4
            boc_4 = add_period(boc_4) if boc_4 else None
            if term and not check_card_exist(deck, term):
                entry = Card(
                    category=cat, term=term, content=content, boc_2=boc_2, 
                    boc_3=boc_3, boc_4=boc_4,create_method=method)
                counter += 1
                session.add(entry)
                deck.cards.append(entry)
                session.commit()
        except Exception as e:
            print(f"Error while saving mcq terms to deck: {e}")
            session.rollback()
    return counter
        
def process_default_terms(session, deck, terms, cat, method, main_opt):
    counter = 0
    x, y = mapping.get(main_opt, ("A", "B"))
    for item in terms:
        try:
            term = item.get(x)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            content = item.get(y)
            content = ' '.join(content) if isinstance(content, list) else content
            content = add_period(content) if content else None
            if term and not check_card_exist(deck, term):
                entry = Card(category=cat, term=term, content=content, create_method=method)
                session.add(entry)
                deck.cards.append(entry)
                counter += 1
                session.commit()
        except Exception as e:
            print(f"Error while saving terms to deck: {e}")
            session.rollback()
    return counter 
def process_discuss_terms(session, deck, terms, cat, method, main_opt):
    x, y, z = mapping.get(main_opt, ("A", "B", "C")) + (None,) * (3 - len(mapping.get(main_opt, ("A", "B", "C"))))
    counter = 0
    for item in terms:
        try:
            term = item.get(x)
            term = ' '.join(term) if isinstance(term, list) else term
            term = term or None
            side_1 = item.get(y)
            side_1 = ' '.join(side_1) if isinstance(side_1, list) else side_1
            side_1 = side_1 or None
            side_2 = item.get(z)
            if z is None:
                side_2 = None
            else:
                side_2 = ' '.join(side_2) if isinstance(side_2, list) else side_2
                side_2 = side_2 or None
            if term and not check_card_exist(deck, term):
                entry = Card(category=cat, term=term, content = side_1, boc_2=side_2, create_method=method)
                session.add(entry)
                deck.cards.append(entry)
                session.commit()
                counter += 1
        except Exception as e:
            print(f"Error while saving discuss terms to deck: {e}")
            session.rollback()
    return counter

def process_formula_terms(session, deck, terms, cat, method, main_opt):
    x, y, z = mapping.get(main_opt, ("A", "B", "C")) + (None,) * (3 - len(mapping.get(main_opt, ("A", "B", "C"))))
    counter = 0
    for item in terms:
        term = item.get(x)
        term = ' '.join(term) if isinstance(term, list) else term
        term = term or None
        formula = item.get(y)
        formula = ' '.join(formula) if isinstance(formula, list) else formula
        formula = "\[" + formula + "\]" if formula else None
        content = item.get(z)
        content = ' '.join(content) if isinstance(content, list) else content
        content = add_period(content) if content else None
        if term and not check_card_exist(deck, term):
            try:
                entry = Card(category=cat, term=term, formula=formula, content=content, create_method=method)
                session.add(entry)
                deck.cards.append(entry)
                session.commit()
                counter += 1
            except Exception as e:
                print(f"Error while saving formula terms to deck: {e}")
                session.rollback()
    return counter
def process_translation(session, deck, terms, prompt_options, method, main_opt, trans_opt):
    trans_opt = prompt_options['trans_opt']
    counter = 0
    if trans_opt is not None:
        name = f"{deck.name}_{method}_Transcribe{trans_opt}_{str(datetime.now(timezone.utc))}"
        create_type = f"{trans_opt} translation"
        transcript_trans = DeckFiles(file_name = name, text_string = terms,
                            time_created=datetime.now(timezone.utc),
                            create_type = create_type)
        counter += 1
        session.add(transcript_trans)
        deck.deck_files.append(transcript_trans)
        session.commit()
        print(f"Transcription {transcript_trans.file_name} created")
    return counter
####  Needs to be checked ####
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
        if card.term.lower() == term.lower():
            print(f"card {term} already exists")
            return True
    return False

def check_subscription_plan(user_id):
    user = User.query.filter_by(id=user_id).first()
    subscription_plan = SubscriptionPlan.query.filter_by(id=user.subscription_plan).first()
    return subscription_plan

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

def log_response_data(prompt, response, content, success, session=None):
    prompt_json = json.dumps(prompt)
    response_json = json.dumps(response)
    content_json = json.dumps(content)
    response_log = ResponseData(prompt=prompt_json,
                            response=response_json, content=content_json, success=success)
    session.add(response_log)
    session.commit()

if __name__ == "__main__":
    with app.app_context():
        async def main():
            num_workers = int(NUM_WORKERS_PROCESSOR)  # Number of concurrent workers to run
            tasks = []
            for _ in range(num_workers):
                task = asyncio.create_task(process_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())