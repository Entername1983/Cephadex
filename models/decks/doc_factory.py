
import datetime as dt
import random
import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.creators.creator import AiCaller
from models.models_ import DeckFiles, Deck, DeckAttributes
from tools.lists import SUMMARY_FILE_NAMES
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

## Creates documents and also in charge of creating deck attributes
class DocFactory:
    def __init__(self, session: 'AsyncSession', deck_id: int):
        self.session: 'AsyncSession' = session
        self.deck: int = deck_id

    def create_doc(self, content:list) -> str:
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

    def save_transcript(self, content:list) -> None:
        deck = self.session.query(Deck).filter_by(id=self.deck).first()
        full_text = "".join(job.processed_content for job in content)
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)}_Audio_Transcript {random.randint(1, 99)}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text, create_type = "Audio Transcript",
                                 time_created = dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        deck.deck_files.append(file_storage)
        self.session.commit()

    def create_deck_attributes(self, text: str) -> 'DeckAttributes':
        ## creates a deck attribute row
        ## assigns relevant attributes to deck if missing, if not just stores the row
        ## One deck can be associated with many attributes
        deck = self.session.query(Deck).filter_by(id=self.deck).first()
        open_ai_caller = AiCaller()
        response = open_ai_caller.extract_deck_attributes(text)
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

    def assign_attributes_to_deck(self, deck: 'Deck', deck_attributes: 'DeckAttributes') -> None:
        if deck.subject is None:
            deck.subject = deck_attributes.subject
        if deck.topic is None:    
            deck.topic = deck_attributes.topic
        if deck.description is None:
            deck.description = deck_attributes.concepts
        self.session.commit()

    async def async_create_doc(self, content:list) -> str:
        print("entered async create doc")
        result = await self.session.execute(
            select(Deck).filter_by(id=self.deck).options(selectinload(Deck.deck_files))
        )
        deck = result.scalars().one()
        full_text = "".join(job.processed_content for job in content)
        task_type = json.loads(content[0].payload)['prompt_options']['main_opt']
        if task_type == "Summarize":
            doc_type = "Summary"
        elif task_type == "Turn2notes":
            doc_type = "Study_Notes"
        else:
            doc_type = "Document"
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)}_{doc_type}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text,
                                create_type=doc_type,
                                time_created=dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage) ## needed?
        await self.session.flush() 
        deck.deck_files.append(file_storage)
        await self.session.commit()
        return full_text

    async def async_save_transcript(self, content:list) -> None:
        result = await self.session.execute(
            select(Deck).filter_by(id=self.deck).options(selectinload(Deck.deck_files))
        )
        deck = result.scalars().one()
        full_text = "".join(job.processed_content for job in content)
        chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} - Audio Transcript {random.randint(1, 99)}"
        file_storage = DeckFiles(file_name=chosen_name, text_string=full_text, create_type="Audio Transcript",
                                 time_created=dt.datetime.now(dt.timezone.utc))
        self.session.add(file_storage)
        await self.session.flush() 
        deck.deck_files.append(file_storage)
        await self.session.commit()

    async def async_create_deck_attributes(self, text: str) -> 'DeckAttributes':
        result = await self.session.execute(select(Deck).filter_by(id=self.deck))
        deck = result.scalar_one()
        open_ai_caller = AiCaller()
        response = await open_ai_caller.extract_deck_attributes(text)
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

    async def async_assign_attributes_to_deck(self, deck: str, deck_attributes: 'DeckAttributes') -> None:
        if deck.subject is None:
            deck.subject = deck_attributes.subject
        if deck.topic is None:
            deck.topic = deck_attributes.topic
        if deck.description is None:
            deck.description = deck_attributes.concepts[:255]
        await self.session.commit()




