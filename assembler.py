from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime
import json
from flask import current_app
from time import sleep
from extractors import add_period
from app import app
from models import Job, Card
from models import DeckFiles, Deck
from models import JobNotification, DeckAttributes, CachedResponse
import asyncio
import random
from extractors import  add_more_cards
import os
import datetime as dt
from helpers import count_tokens, split_text
from extractors import extract_deck_attributes
from datetime import timezone
from lists import SUMMARY_FILE_NAMES
from itertools import groupby
from sqlalchemy.exc import IntegrityError
import openai


SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")
SQLALCHEMY_ENGINE_OPTIONS = json.loads(os.environ['SQLALCHEMY_ENGINE_OPTIONS'])
CONST_PLAN = os.environ.get("CONST_PLAN")
NUM_WORKERS_ASSEMBLER = int(os.environ.get("NUM_WORKERS_ASSEMBLER"))


ACCEPTABLE_ERROR_RATIO = 0.2
DENOMINATOR_CHECK_FLASHCARDS = 100


async def process_jobs():

    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    while True:
        with session_factory() as session:
            try:
            ## looks through the JobNotification table and finds a queued job notification.  Changes the status to processing and returns that job notification
                job_notification = find_queued_notifications(session)
                if job_notification:
                ## looks through the jobs associated with the job notification and checks if all jobs are complete.  Return number of jobs completed + flashcards created
                    result = check_if_jobs_are_done(job_notification)
                    print(result)
                    if result is not None:
                        print("result not none")
                        completed, flashcard_counter, errors, jobs = result
                        # Check if the result is not None before unpacking
                        if flashcard_counter:
                            ## Checks for significant errors
                            check_for_errors(errors, completed)
                            ## Assembles long form files
                            result = reassemble_long_form(jobs, session)
                            ## Assemble audio transcript
                            if job_notification.input_details in [".mp3", ".wav"]:
                                print("recognized audio transcription in need of re-assembly")
                                reassemble_audio_transcript(jobs, session)
                            if result is not None:
                                full_text, deck_id = result            
                            ##Creates a deck attribute row by sending the first 3000 tokens of the long form to open AI
                            attributes = await create_deck_attributes(full_text, deck_id, session)
                            print(attributes)
                            deck_attributes = session.query(DeckAttributes).filter_by(id=attributes).first()

                            try:
                                assign_attributes_to_deck(deck_id, deck_attributes, session)
                            except Exception as e:
                                print ("error assigning attributes to deck", e)
                            print(attributes)
                            ## checks if the JobNotif has extract_type needed to check for flashcards
                            if check_for_flashcards_type(job_notification.extract_type):
                                if not check_sufficient_cards_created(flashcard_counter, job_notification.cost):
                                    print("not enough cards created")
                                    subject = deck_attributes.subject
                                    topic = deck_attributes.topic
                                    concepts = deck_attributes.concepts
                                    grade = deck_attributes.grade
                                    x = await more_cards_please(subject, topic, concepts, grade, job_notification)
                                    method = "extra"
                                    save_terms_to_deck(deck_id, x, job_notification.extract_type, method, session)

                    ## change job notification back to queued
                            change_job_notification_to_ready(job_notification, session)
                            cache_it(jobs, session, job_notification, deck_attributes)
                    else:
                        job_notification.state = 'queued'
                        session.commit()
            except Exception as e:
                print(e)
                session.rollback()
        sleep(10)


async def more_cards_please(subject, topic, concepts, grade, job_notification):
    with current_app.app_context():
        x = await add_more_cards(subject, topic, concepts, grade, job_notification.extract_type)
    return x


def cache_it(jobs, session, job_notification, deck_attributes):
    input_type = job_notification.input_details
    print("entered cache it")
    try:
        jobs = sorted(jobs, key=lambda x: x.task_type)
        grouped_objects = groupby(jobs, key=lambda x: x.task_type)
        for key, group in grouped_objects:
            output_data = []
            input_text = []
            output_type = key
            for item in group:
                output_data.append(item.processed_content)
                input_text.append(item.payload)
            output_data = "#,#,# ".join(map(str, output_data))
            input_text = "#,#,# ".join(map(str, input_text))
            output_data = output_data[:20000]
            input_text = input_text[:1000]
            try:
                cached_response = CachedResponse(input_type=input_type,
                    input_text=input_text, output_type=output_type,
                    output_data=output_data,
                    date_created = datetime.now(timezone.utc),
                    subject = deck_attributes.subject, topic = deck_attributes.topic,
                    concepts = deck_attributes.concepts,
                    difficulty = deck_attributes.difficulty,) 
                session.add(cached_response)
            except IntegrityError as e:
                print("duplicate entry leading to integrity error ", e)

        session.commit()
    except Exception as e:
        print(e)
        session.rollback()

def assign_attributes_to_deck(deck_id, deck_attributes, session):
    print("entered assign attributes to deck")
    deck = session.query(Deck).filter_by(id=deck_id).first()
    print("deck is ", deck)
    if deck.subject is None:
        deck.subject = deck_attributes.subject
    if deck.topic is None:    
        deck.topic = deck_attributes.topic
    if deck.description is None:
        deck.description = deck_attributes.concepts
    session.commit()

def change_job_notification_to_ready(job_notification, session):
    print("entered change job notification to ready")
    job_notification.state = 'ready'
    session.commit()

def find_queued_notifications(session):
    with current_app.app_context():

        print("entered find notification")
        ## looks through the JobNotification table and finds a queued job notification.  Changes the status to processing and returns that job notification
        job_notification = session.query(JobNotification).filter_by(state='queued').first()
        print(job_notification)
        if job_notification:
            print("found job notification", job_notification.id)
            job_notification.state = 'processing'
            session.commit()
            return job_notification
        else: 
            return None


def check_if_jobs_are_done(job_notification):
    with current_app.app_context():
        print("entered check if jobs are done")
        completed_counter = 0
        flashcard_counter = 1
        errors = 0
        jobs = Job.query.filter_by(slug=job_notification.slug).all()
        print(jobs)
        for job in jobs:
            if job.state == 'completed':
                completed_counter += 1
                flashcard_counter += job.qty_cards_created
                if job.error_type != None:
                    errors += 1
        ## if length of jobs == completed counter, then all jobs are done
        if len(jobs) == completed_counter:
            print("all jobs complete")
            return completed_counter, flashcard_counter, errors, jobs

def check_for_errors(errors, completed):
    print("error check")
    if errors / completed > ACCEPTABLE_ERROR_RATIO:
        pass

def reassemble_long_form(jobs, session):
    print("enter reassembling long form")
    try:
        deck = Deck.query.get_or_404(jobs[0].deck_id)
        print(deck)
        full_text = "".join(
            job.processed_content
            for job in jobs
            if job.task_type == "Summarize")

        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - Summary"
        name = f"{chosen_name} "
        file_storage = DeckFiles(file_name=name, text_string=full_text,
                                create_type = "Summary",
                                time_created = dt.datetime.now(dt.timezone.utc))
        print(file_storage)
        deck = session.merge(deck)
        file_storage = session.merge(file_storage)

        session.add(file_storage)
        print("1")
        deck.deck_files.append(file_storage)
        print("2")
        session.commit()
        print("DECK FILE")
        print(file_storage.id)
        print(full_text)
        return full_text, deck.id
    except Exception as e:
        print(f"Error creating file {e}")

def reassemble_audio_transcript(jobs, session):
    print("enter reassembling long form")
    try:
        deck = Deck.query.get_or_404(jobs[0].deck_id)
        print(deck)
        full_text = "".join(
            job.processed_content
            for job in jobs
            if job.task_type == "audio")

        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} Audio Transcript"
        rand_int = random.randint(1, 99)
        name = f"{chosen_name} {rand_int}"
        file_storage = DeckFiles(file_name=name, text_string=full_text,
                                create_type = "Audio Transcript",
                                time_created = dt.datetime.now(dt.timezone.utc))
        print(file_storage)
        deck = session.merge(deck)
        file_storage = session.merge(file_storage)

        session.add(file_storage)
        print("1")
        deck.deck_files.append(file_storage)
        print("2")
        session.commit()
        print("DECK FILE")
        print(file_storage.id)
        print(full_text)
        return full_text, deck.id
    except Exception as e:
        print(f"Error creating file {e}")


async def create_deck_attributes(full_text, deck_id, session):
    with current_app.app_context():

        print("entered create deck attributes")
        text = limit_text(full_text)
        ## send text to open AI and get attributes 
        response = await extract_deck_attributes(text)
        print(response)
        subject = response['subject']
        topic = response['topic']
        concepts = ", ".join(response['concepts'])
        difficulty = response['difficulty']
        attributes = DeckAttributes(deck_id=deck_id,
                subject=subject, topic=topic, concepts=concepts, grade=difficulty)
        session.add(attributes)
        session.commit()
        return attributes.id

def limit_text(full_text):
    print("entered limit text")
    print(full_text)
    print(count_tokens(full_text))
    
    if count_tokens(full_text) > 3000:
        text = split_text(full_text, 3000)
        print(text)
        return text[0]
    return full_text

def check_for_flashcards_type(task_type):
    if task_type in ['Definitions', 'Theories', 'Cloze', 'Mcq', 'Comprehension', 'Formulas', 'Explain', 'Discuss']:
        print("recognized deck type as relevant to flashcard recreation")
        return True

def check_sufficient_cards_created(flashcard_counter, cost):
    if flashcard_counter > cost / DENOMINATOR_CHECK_FLASHCARDS:
        print("sufficient cards created")
        return True

##### functions re-used from extractors.py 
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

def save_terms_to_deck(deck_id, terms, main_opt , method="extract", session=None):
    deck = Deck.query.get_or_404(deck_id)
    print("entered save terms to deck")
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
                entry = session.merge(entry)
                deck = session.merge(deck)
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
                entry = session.merge(entry)
                deck = session.merge(deck)
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
                entry = session.merge(entry)
                deck = session.merge(deck)
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
                entry = session.merge(entry)
                deck = session.merge(deck)
                session.add(entry)
                deck.cards.append(entry)
                session.commit()
                counter += 1
            except Exception as e:
                print(f"Error while saving formula terms to deck: {e}")
                session.rollback()
    return counter


def check_card_exist(deck, term):
    deck = Deck.query.filter_by(id=deck.id).first()
    for card in deck.cards:
        if card.term.lower() == term.lower():
            print(f"card {term} already exists")
            return True
    return False



if __name__ == "__main__":
    with app.app_context():
        async def main():
            num_workers = 2 ##int(NUM_WORKERS_ASSEMBLER)
            tasks = []
            for _ in range(num_workers):
                task = asyncio.create_task(process_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())