
import asyncio
import json
import logging

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models.decks.doc_factory import DocFactory
from models.creators.creator import AiCaller
from dotenv import load_dotenv
from models.jobs.job_processor import JobProcessor
from models.jobs.job_finder import JobFinder
from models.jobs.jobs_config import (MAX_CONCURRENT_TASKS,
    ASYNC_SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS,
    LONG_FORM_JOBS, DENOMINATOR_CHECK_FLASHCARDS)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.models_ import JobNotification, DeckAttributes, Job
from models.helpers.log_decorators import job_log_decorator

from models.exceptions.exceptions import ProcessingJobError, ProcessingCompletionError


processing_logger = logging.getLogger("job_processing")

load_dotenv()
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class JobBatch():
    def __init__(self, slug: str):
        self.slug: str = slug
        self.jobs: list = []
        self.failed_jobs: list = []
        self.error_ratio: float = 0
        self.doc_creator: DocFactory = None
        self.text: str = None
        self.attributes: DeckAttributes = None
        self.job_notification: JobNotification = None
        self.card_created: int = 0
        self.sufficient_cards: bool = True

    def add_job(self, job: 'Job') -> None:
        self.jobs.append(job)

    @job_log_decorator
    async def process(self) -> None:
        self.deck_id = self.jobs[0].deck_id
        try:
            tasks = [self.process_job_with_semaphore(job) for job in self.jobs]
            await asyncio.gather(*tasks)
            await self.handle_completion()
        except Exception as e:
             processing_logger.error(f"Error processing job batch: {e}")            
             raise e
        
    async def process_job_with_semaphore(self, job: 'Job') -> None:
        async with semaphore:
            async with session_factory() as session:
                try:
                    merged_job = await session.merge(job)
                    job_to_process = JobProcessor(merged_job, session)
                    await job_to_process.process()
                    merged_job.state = "completed"
                    await session.commit()
                    await session.refresh(merged_job)
                    job.state = merged_job.state
                    job.processed_content = merged_job.processed_content
                    job.qty_cards_created = merged_job.qty_cards_created

                except Exception as e:
                    processing_logger.error(f"Error processing job with semaphore: {e}")
                    self.failed_jobs.append(merged_job)
                    merged_job.state = "error"
                    await session.commit()
                    raise ProcessingJobError(e) from e
    
    async def handle_completion(self) -> None:
        async with session_factory() as session:
            try:
                job_notification = await JobFinder.find_pending_notification(session, self.slug)
                self.job_notification = job_notification
                self.doc_creator = DocFactory(session, self.deck_id)
                task_type = self.jobs[0].task_type
                if task_type == "audio":
                    await self.reassemble_audio_transcript()
                else:
                    await self.reassemble_long_form()
                    await self.create_deck_attributes()
                    await self.check_sufficient_cards_created()
                    if self.sufficient_cards is False:
                        await self.add_more_cards()
                    await self.change_notification_to_ready(session)
                    await self.cache_results(session)
            except Exception as e:
                processing_logger.error(f"Error handling completion: {e}")
                raise ProcessingCompletionError(e) from e

    async def check_for_errors(self) -> None:
        error_ratio = len(self.failed_jobs) / len(self.jobs)
        self.error_ratio = error_ratio

    async def reassemble_long_form(self) -> None:
        if long_form_jobs := [
            job for job in self.jobs if job.task_type in LONG_FORM_JOBS
        ]:  
            self.text = await self.doc_creator.async_create_doc(long_form_jobs)

    async def reassemble_audio_transcript(self) -> None:
        audio_jobs = []
        for job in self.jobs:
            if job.task_type == "audio":
                audio_jobs.append(job)
                self.jobs.remove(job)
        if audio_jobs:
            await self.doc_creator.async_save_transcript(audio_jobs)

    async def create_deck_attributes(self) -> None:
        if self.text is None:
            self.text = json.loads(self.jobs[0].payload)['text']
        self.attributes = await self.doc_creator.async_create_deck_attributes(self.text)

    async def check_sufficient_cards_created(self) -> None:
        for job in self.jobs:
            self.card_created += job.qty_cards_created
        if self.card_created < self.job_notification.cost / DENOMINATOR_CHECK_FLASHCARDS:
            self.sufficient_cards = False

    async def add_more_cards(self) -> None:
        open_ai_caller = AiCaller()
        await open_ai_caller.add_more_cards(self.attributes)

    async def change_notification_to_ready(self, session: AsyncSession) -> None:
        self.job_notification.state = "ready"
        await session.commit()

    async def cache_results(self, session: AsyncSession) -> None:
        pass
