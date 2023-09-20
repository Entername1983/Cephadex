import os
import json
import logging 
from sqlalchemy import select
from models.models_ import Deck, Job
from models.creators.creator import AiCaller
from models.decks.card_factory import CardFactory
from models.jobs.jobs_config import LONG_FORM_JOBS
from typing import TYPE_CHECKING
from typing import Dict, Union
from models.helpers.log_decorators import job_log_decorator
processing_logger = logging.getLogger("job_processing")

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class JobProcessor():
    def __init__(self, job: Job, session: 'AsyncSession'):
        self.session: AsyncSession = session 
        self.job: Job = job 
        self.slug: str = job.slug 
        self.payload: Dict[str, Union[str, None]] = json.loads(job.payload)
        self.text: Union[str, None] = self.payload.get('text', None)
        self.segment: Union[str, None] = self.payload.get('segment', None)
        self.openai_caller: AiCaller = AiCaller()

    @job_log_decorator
    async def process(self):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:  
                if self.payload['task_type'] == 'audio':
                    await self.process_audio_job()
                elif self.payload['task_type'] == 'standard':
                    await self.process_standard_job()
                break  
            except Exception as e:
                processing_logger.error(f"Error occurred while in attempt {attempt} JobProcessor.process, slug:{self.job.slug}: {str(e)}")  # noqa: E501
                if attempt == max_attempts: 
                    processing_logger.error(f"Max attempts reached, raising error and abandonning job slug:{self.job.slug}: {str(e)}") # noqa: E501
                    raise e
                
    @job_log_decorator
    async def process_audio_job(self) -> None:
        segment = self.payload['segment']
        if not os.path.exists(segment):
            processing_logger.error(f"Error in process audio The file '{segment}' does not exist.")
        text = await self.openai_caller.transcribe_whisper(segment)
        self.text = text
        try:
            os.remove(segment)
        except OSError as e:
            processing_logger.error(f"Error occurred while deleting the audio file '{segment}': {str(e)}")
        new_payload = {'deck': self.payload['deck'], 'text': text,
                                'prompt_options': self.payload['prompt_options'], 'task_type': "standard"}
        new_job = Job(slug=self.slug, task_type="standard",
            payload = json.dumps(new_payload), state="queued",
            item_number = self.job.item_number, item_quantity = self.job.item_quantity,
            deck_id = self.payload['deck'], processed_content = text
        )
        if self.payload['prompt_options']['main_opt'] not in LONG_FORM_JOBS:
            task = None
            if self.payload['prompt_options']['create_summary_opt'] is True:
                task = "Summarize"
            elif self.payload['prompt_options']['create_notes_opt'] is True:
                task = "Turn2notes"
            if task:
                prompt_options = self.payload['prompt_options'].copy()
                prompt_options['main_opt'] = task
                summary_payload = {'deck': self.payload['deck'], 'text': text,
                                    'prompt_options': prompt_options, 'task_type': "standard"}
                long_form_job = Job(slug=self.slug, task_type="standard",
                    payload = json.dumps(summary_payload), state="queued",
                    item_number = self.job.item_number, item_quantity = self.job.item_quantity,
                    deck_id = self.payload['deck']
                )
                self.session.add(long_form_job)
        self.job.state = "completed"
        self.job.processed_content = text
        ##self.job.save_source = self.payload['prompt_options']['save_text_opt']
        self.session.add(new_job)
        await self.session.commit()
        
    async def process_standard_job(self) -> None:
        if self.payload['prompt_options']['main_opt'] in ["Transcribe", "Turn2notes", "Summarize"]:
            await self.handle_long_form()
        else:
            await self.handle_extract_terms()
        if self.payload['prompt_options']['images_opt']:
            await self.handle_images()

    @job_log_decorator
    async def handle_long_form(self) -> None:
        if self.payload['prompt_options']['main_opt'] == "Transcribe":
            response = await self.openai_caller.transcribe_whisper(self.text)
        elif self.payload['prompt_options']['main_opt'] == "Turn2notes":
            response = await self.openai_caller.turn_to_notes(self.text)
        elif self.payload['prompt_options']['main_opt'] == "Summarize":
            response = await self.openai_caller.summarize(self.text)
        if response:
            self.job.processed_content = response
        await self.session.commit()

    @job_log_decorator
    async def handle_extract_terms(self) -> None:
        try:
            response = await self.openai_caller.extract_terms(self.text, self.payload['prompt_options'])
        except Exception as e:
            processing_logger.error(f"Error occurred while extracting terms: {str(e)}")
            raise e
        try:
            result = await self.session.execute(select(Deck).filter_by(id=self.payload['deck']))
            deck = result.scalar_one()
            card_factory = CardFactory(self.session, deck)
            await card_factory.async_create_cards(response, self.payload['prompt_options']['main_opt'])
            self.job.processed_content = str(response)
            self.job.qty_cards_created = card_factory.card_counter
            await self.session.commit()
        except Exception as e:
            processing_logger.error(f"Error occurred while creating cards: {str(e)}")
            raise e

    async def handle_images(self) -> None:
        pass