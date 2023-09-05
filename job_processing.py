
import asyncio
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from models.models_ import (
    Deck, Job, JobNotification, UserSettings, SharedDecks, User, Group,
    Game, Card
)
from dotenv import load_dotenv
from models.jobs.job_batch import JobBatch
from models.jobs.job_finder import JobFinder
from models.jobs.jobs_config import (
    ASYNC_SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS
    )
from run.logger_setup import setup_processing_logger
from models.helpers.log_decorators import job_log_decorator
import os
load_dotenv()

processing_logger = setup_processing_logger()

SLEEP_TIME = os.environ.get('SLEEP_TIME', 5)

engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URI, **SQLALCHEMY_ENGINE_OPTIONS)
session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@job_log_decorator
async def process_jobs() -> None:
    """ Main job_processing function.  Here we find all pending jobs, put them into batches,
    create a JobBatch object for each batch, and then process each batch.
    """
    while True:
        async with session_factory() as session:
            try:
                jobs = await JobFinder.find_pending_jobs(session)
            except Exception as find_exc:
                processing_logger.error(f"Error finding pending jobs: {find_exc}")
            batched_jobs = {}
            if jobs:
                for job in jobs:
                    job.state = 'pending'
                    slug = job.slug
                    if slug not in batched_jobs:
                        batched_jobs[slug] = JobBatch(slug)
                    batched_jobs[slug].add_job(job)
                try:
                    await session.commit()
                except Exception as commit_exc:
                    processing_logger.error(f"Failed to commit JobBatch to db: {commit_exc}")
        for batch in batched_jobs.values():
            asyncio.create_task(batch.process())
        await asyncio.sleep(SLEEP_TIME) 

if __name__ == "__main__":
    print("Starting job processing")
    asyncio.run(process_jobs())

