
import asyncio
import os
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models.decks.deck import Deck
from models.decks.job import Job
from models.decks.job_notification import JobNotification
from models.groups.group import Group ## NECESSARY
from models.creators import * ## NECESSARY
from models.decks import * ## NECESSARY
from models.exceptions import * ## NECESSARY
from models.extractors import * ## NECESSARY
from models.games import * ## NECESSARY
from models.groups import * ## NECESSARY
from models.user.user import * ## NECESSARY
from models.decks.doc_factory import DocFactory
from models.creators.creator import OpenAiCaller
from models.decks.card_factory import CardFactory
from dotenv import load_dotenv

load_dotenv()
ASYNC_SQLALCHEMY_DATABASE_URI = os.environ.get("ASYNC_SQLALCHEMY_DATABASE_URI")
SQLALCHEMY_ENGINE_OPTIONS = json.loads(os.environ['SQLALCHEMY_ENGINE_OPTIONS'])
CONST_PLAN = os.environ.get("CONST_PLAN")
NUM_WORKERS_PROCESSOR = os.environ.get("NUM_WORKERS_PROCESSOR")
SLEEP_TIME = int(os.environ.get("SLEEP_TIME"))
MAX_CONCURRENT_TASKS = 1
ACCEPTABLE_ERROR_RATIO = 0.2
DENOMINATOR_CHECK_FLASHCARDS = 100
LONG_FORM_JOBS = ["Summarize, Turn2notes, Transcribe"]

semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
async def process_jobs():
    while True:
        async with session_factory() as session:
            jobs = await JobFinder.find_pending_jobs(session)
            # Group jobs by slug into JobBatch objects
            batched_jobs = {}
            for job in jobs:
                slug = job.slug
                if slug not in batched_jobs:
                    batched_jobs[slug] = JobBatch(slug)
                batched_jobs[slug].add_job(job)

                job.state = 'pending'
                await session.commit()
            # Process batches concurrently
            for batch in batched_jobs.values():
                asyncio.create_task(batch.process())
        await asyncio.sleep(88) 

class JobBatch():
    def __init__(self, slug):
        self.slug = slug
        self.jobs = []
        self.failed_jobs = []
        self.error_ratio = 0
        self.doc_creator = None
        self.text = None
        self.attributes = None
        self.job_notification = None
        self.card_created = 0
        self.sufficient_cards = True

    def add_job(self, job):
        self.jobs.append(job)

    async def process(self):
        print("Processing batch...")
        self.deck_id = self.jobs[0].deck_id
        try:
            tasks = [self.process_job_with_semaphore(job) for job in self.jobs]
            await asyncio.gather(*tasks)
            await self.handle_completion()
        except Exception as e:
            print(f"Error occurred while processing batch: {str(e)}")

    async def process_job_with_semaphore(self, job):
        print("Processing job with sempahore")
        async with semaphore:
            async with session_factory() as session:
                job_to_process = JobProcessor(job, session)
                result = await job_to_process.process()
                if result == "Failed":
                    self.failed_jobs.append(job)

    async def handle_completion(self):
        print("Handling batch completion...")
        async with session_factory() as session:
            job_notification = await JobFinder.find_pending_notification(session, self.slug)
             
            print(f"Job notification: {job_notification}")
            self.job_notification = job_notification
            self.doc_creator = DocFactory(session, self.deck_id)
            task_type = self.jobs[0].task_type
            if task_type == "audio":
                await self.async_reassemble_audio_transcript()
            else:
                await self.reassemble_long_form()
                await self.create_deck_attributes()
                await self.check_sufficient_cards_created()
                if self.sufficient_cards is False:
                    await self.add_more_cards()
                await self.change_notification_to_ready(session)
                await self.cache_results(session)

    async def check_for_errors(self):
        print("Checking for errors...")
        error_ratio = len(self.failed_jobs) / len(self.jobs)
        print(f"Error ratio: {error_ratio}")
        self.error_ratio = error_ratio

    async def reassemble_long_form(self):
        print("Reassembling long form...")
        long_form_jobs = []
        for job in self.jobs:
            if job.task_type in LONG_FORM_JOBS:
                long_form_jobs.append(job)
        if long_form_jobs:
            self.text = await self.doc_creator.async_create_doc(long_form_jobs)

    async def reassemble_audio_transcript(self):
        print("Reassembling audio transcript...")
        audio_jobs = []
        for job in self.jobs:
            if job.task_type == "audio":
                audio_jobs.append(job)
                self.jobs.remove(job)
        if audio_jobs:
            await self.doc_creator.async_save_transcript(audio_jobs)

    async def create_deck_attributes(self):
        print("Creating deck attributes...")
        if self.text is None:
            self.text = json.loads(self.jobs[0].payload)['text']
        
        self.attributes = await self.doc_creator.async_create_deck_attributes(self.text)

    async def check_sufficient_cards_created(self):
        print("Checking sufficient cards created...")
        print(self.job_notification)
        for job in self.jobs:
            self.card_created += job.qty_cards_created
        if self.card_created < self.job_notification.cost / DENOMINATOR_CHECK_FLASHCARDS:
            self.sufficient_cards = False

    async def add_more_cards(self):
        print("Adding more cards...")
        open_ai_caller = OpenAiCaller()
        await open_ai_caller.add_more_cards(self.attributes)

    async def change_notification_to_ready(self, session):
        print("Changing notification to ready...")
        self.job_notification.state = "ready"
        await session.commit()

    async def cache_results(self, session):
        print("Caching results...")
        pass

class JobFinder():
    @staticmethod
    async def find_pending_jobs(session):
        print("Finding pending jobs...")
        result = await session.execute(select(Job).filter_by(state="queued"))
        return result.scalars().all()
    
    @staticmethod
    async def find_pending_notifications(session):
        print("Finding pending notifications...")
        result = await session.execute(select(JobNotification).filter_by(state="queued"))
        return result.scalars_one()
    
    @staticmethod
    async def find_pending_notification(session, slug):
        print("Finding pending notification...")
        result = await session.execute(select(JobNotification).filter_by(state="queued", slug=slug))
        return result.scalar_one()
    
class JobProcessor():
    def __init__(self, job, session):
        self.session = session
        self.job = job
        self.slug = job.slug
        self.payload = json.loads(job.payload)
        self.text =self.payload.get('text', None)
        self.segment = self.payload.get('segment', None)
        self.openai_caller = OpenAiCaller()

    async def process(self):
        print("Processing job...")
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                self.job.state = "processing"
                if self.payload['task_type'] == 'audio':
                    await self.process_audio_job()
                elif self.payload['task_type'] == 'standard':
                    await self.process_standard_job()
                self.job.state = "completed"            
                await self.session.commit()
                break  # Exit the loop if successful
            except Exception as e:
                print(f"Attempt {attempt} failed: {str(e)}")
                if attempt == max_attempts:  # Check if it's the last attempt
                    self.job.state = "failed"
                    await self.session.commit()
                    return "Failed"

    async def process_audio_job(self):
        print("Processing audio job...")
        segment = self.payload['segment']
        text = await  self.openai_caller.transcribe_whisper(segment)
        self.text = text
        try:
            os.remove(segment)
            print(f"File '{segment}' has been successfully deleted.")
        except OSError as e:
            print(f"Error occurred while deleting the file '{segment}': {str(e)}")
        new_payload = {'deck': self.payload['deck'], 'text': text,
                                'prompt_options': self.payload['prompt_options']}
        new_job = Job(slug=self.slug, user = self.payload['user'], task_type="standard",
            payload = json.dumps(new_payload), state="queued",
            item_number = self.job.item_number, item_quantity = self.job.item_quantity,
            deck_id = self.payload['deck'], processed_content = text
        )
        self.job.state = "completed"
        self.job.processed_content = text
        self.job.save_source = True
        self.session.add(new_job)
        await self.session.commit()
        
    async def process_standard_job(self):
        print("Processing standard job...")
        if self.payload['prompt_options']['main_opt'] in ["Transcribe", "Turn2notes", "Summarize"]:
            await self.handle_long_form()
        else:
            await self.handle_extract_terms()
        if self.payload['prompt_options']['images_opt']:
            await self.handle_images()

    async def handle_long_form(self):
        print("Handling long form...")
        if self.payload['main_opt'] == "Transcribe":
            response = await self.openai_caller.transcribe_whisper(self.text)
        elif self.payload['main_opt'] == "Turn2notes":
            response = await self.openai_caller.turn_to_notes(self.text)
        elif self.payload['main_opt'] == "Summarize":
            response = await self.openai_caller.summarize(self.text)
        if response:
            self.job.processed_content = response
        await self.session.commit()

    async def handle_extract_terms(self):
        print("Handling extract terms...")
        response = await self.openai_caller.extract_terms(self.text, self.payload['prompt_options'])
        result = await self.session.execute(select(Deck).filter_by(id=self.payload['deck']))
        deck = result.scalar_one()
        card_factory = CardFactory(self.session, deck)
        await card_factory.async_create_cards(response, self.payload['prompt_options']['main_opt'])
        self.job.qty_cards_created = card_factory.card_counter
        await self.session.commit()

    async def handle_images(self):
        pass

if __name__ == "__main__":
    asyncio.run(process_jobs())