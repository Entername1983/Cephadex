import os
import json
from sqlalchemy import select
from models.decks.deck import Deck
from models.decks.job import Job
from models.creators.creator import AiCaller
from models.decks.card_factory import CardFactory


class JobProcessor():
    def __init__(self, job, session):
        self.session = session
        self.job = job
        self.slug = job.slug
        self.payload = json.loads(job.payload)
        self.text =self.payload.get('text', None)
        self.segment = self.payload.get('segment', None)
        self.openai_caller = AiCaller()

    async def process(self):
        print("Processing job...")
        max_attempts = 3
        print(self.session)
        for attempt in range(1, max_attempts + 1):
            try:  
                if self.payload['task_type'] == 'audio':
                    await self.process_audio_job()
                elif self.payload['task_type'] == 'standard':
                    await self.process_standard_job()
                break  # Exit the loop if successful
            except Exception as e:
                print(f"Attempt {attempt} failed: {str(e)}")
                if attempt == max_attempts:  # Check if it's the last attempt
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
        if self.payload['prompt_options']['main_opt'] == "Transcribe":
            print("Transcribing...")
            response = await self.openai_caller.transcribe_whisper(self.text)
        elif self.payload['prompt_options']['main_opt'] == "Turn2notes":
            print("Turning to notes...")
            response = await self.openai_caller.turn_to_notes(self.text)
        elif self.payload['prompt_options']['main_opt'] == "Summarize":
            print("Summarizing...")
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