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

def process_jobs():
    engine = create_engine(SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
    session_factory = scoped_session(sessionmaker(bind=engine))
    while True:
        with session_factory() as session:
            jobs = await find_jobs(session)


def find_jobs(session):
    with current_app.app_context():
        try:
            ## find jobs where state si completed and result is 0
            job_completed = Job.query.filter_by(state='completed', result=0).first()
            ## find all jobs with same slug as job_completed
            jobs = Job.query.filter_by(slug=job_completed.slug).all()
            ## find all jobs with same slug as job_completed and result is 0 and state completed
            jobs_completed = Job.query.filter_by(slug=job_completed.slug, result=0, state='completed').all()
            if jobs.count() == jobs_completed.count():
                for job in jobs:
                    job.result = '1'
                session.commit()
                return jobs_completed
        except Exception as e:
            print(f"Error while finding pending job for reassembly: {e}")
            session.rollback()
            return None






if __name__ == "__main__":
    with app.app_context():
        def main():
            num_workers = 5  # Number of concurrent workers to run
            tasks = []
            for i in range(num_workers):
                task = asyncio.create_task(assemble_jobs())
                tasks.append(task)
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)

        asyncio.run(main())