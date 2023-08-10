
import datetime as dt
import random
from sqlalchemy import select
from models.creators.creator import OpenAiCaller
from .deck_files import DeckFiles

from .deck import Deck
from .deck_attributes import DeckAttributes
from lists import SUMMARY_FILE_NAMES


class DocFactory:
    def __init__(self, session, deck_id):
        self.session = session
        self.deck = deck_id

    def create_doc(self, content:list):
        print("entered create doc...")
        deck = self.session.query(Deck).filter_by(id=self.deck).first()
        full_text = "".join(job.processed_content for job in content)
        task_type = content[0].task_type
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - {task_type}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text,
                                create_type = task_type,
                                time_created = dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        deck.deck_files.append(file_storage)
        self.session.commit()
        return full_text



    def save_transcript(self, content:list):
        print("entered save transcript...")
        deck = self.session.query(Deck).filter_by(id=self.deck).first()
        full_text = "".join(job.processed_content for job in content)
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - Audio Transcript {random.randint(1, 99)}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text, create_type = "Audio Transcript",
                                 time_created = dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        deck.deck_files.append(file_storage)
        self.session.commit()

    def create_deck_attributes(self, text):
        ## creates a deck attribute row
        ## assigns relevant attributes to deck if missing, if not just stores the row
        ## One deck can be associated with many attributes
        print("entered create deck attributes...")
        deck = self.session.query(Deck).filter_by(id=self.deck).first()
        open_ai_caller = OpenAiCaller()
        response = open_ai_caller.extract_deck_attributes(text)
        print(response)
        subject = response['subject']
        topic = response['topic']
        concepts = ", ".join(response['concepts'])
        difficulty = response['difficulty']
        language = response['language']
        attributes = DeckAttributes(deck_id=self.deck,
                subject=subject, topic=topic, concepts=concepts,
                grade=difficulty, language = language)
        self.session.add(attributes)
        self.session.commit()
        self.assign_attributes_to_deck(deck, attributes)
        return attributes


    def assign_attributes_to_deck(self, deck, deck_attributes):
        print("entered assign attributes to deck")
        print("deck is ", deck)
        if deck.subject is None:
            deck.subject = deck_attributes.subject
        if deck.topic is None:    
            deck.topic = deck_attributes.topic
        if deck.description is None:
            deck.description = deck_attributes.concepts
        self.session.commit()




    async def async_create_doc(self, content:list) -> str:
        print("entered async create doc...")
        deck = await self.session.execute(select(Deck).filter_by(id=self.deck))
        full_text = "".join(job.processed_content for job in content)
        task_type = content[0].task_type
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - {task_type}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text,
                                create_type=task_type,
                                time_created=dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        deck.deck_files.append(file_storage)
        await self.session.commit()
        return full_text

    async def async_save_transcript(self, content:list):
        print("entered async save transcript...")
        deck = await self.session.execute(select(Deck).filter_by(id=self.deck))
        full_text = "".join(job.processed_content for job in content)
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - Audio Transcript {random.randint(1, 99)}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text, create_type="Audio Transcript",
                                 time_created=dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        deck.deck_files.append(file_storage)
        await self.session.commit()

    async def async_create_deck_attributes(self, text):
        print("entered async create deck attributes...")
        result = await self.session.execute(select(Deck).filter_by(id=self.deck))
        deck = result.scalar_one()
        open_ai_caller = OpenAiCaller()
        response = await open_ai_caller.extract_deck_attributes(text)
        print(response)
        subject = response['subject']
        topic = response['topic']
        concepts = ", ".join(response['concepts'])
        difficulty = response['difficulty']
        language = response['language']
        attributes = DeckAttributes(deck_id=self.deck,
                                    subject=subject, topic=topic, concepts=concepts,
                                    grade=difficulty, language=language)
        self.session.add(attributes)
        await self.session.commit()
        await self.async_assign_attributes_to_deck(deck, attributes)
        return attributes

    async def async_assign_attributes_to_deck(self, deck, deck_attributes):
        print("entered async assign attributes to deck")
        print("deck is ", deck)
        if deck.subject is None:
            deck.subject = deck_attributes.subject
        if deck.topic is None:
            deck.topic = deck_attributes.topic
        if deck.description is None:
            deck.description = deck_attributes.concepts
        await self.session.commit()