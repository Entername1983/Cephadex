
import asyncio
import os
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models.decks.deck import Deck
from models.decks.job import Job
from models.decks.job_notification import JobNotification
from models.group.group import Group ## NECESSARY
from models.creators import * ## NECESSARY
from models.decks import * ## NECESSARY
from models.exceptions import * ## NECESSARY
from models.extractors import * ## NECESSARY
from models.games import * ## NECESSARY
from models.group import * ## NECESSARY
from models.user.user import * ## NECESSARY

from dotenv import load_dotenv

from models.jobs.job_batch import JobBatch
from models.jobs.job_finder import JobFinder
from models.jobs.jobs_config import ASYNC_SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, MAX_CONCURRENT_TASKS

load_dotenv()



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
                job.state = 'pending'
                
                slug = job.slug
                if slug not in batched_jobs:
                    batched_jobs[slug] = JobBatch(slug)
                batched_jobs[slug].add_job(job)
            await session.commit()
                
                
        # Process batches concurrently
        for batch in batched_jobs.values():
            asyncio.create_task(batch.process())
        await asyncio.sleep(30) 

if __name__ == "__main__":
    asyncio.run(process_jobs())