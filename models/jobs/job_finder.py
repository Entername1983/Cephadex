
from sqlalchemy import select
from models.decks.job import Job
from models.decks.job_notification import JobNotification


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