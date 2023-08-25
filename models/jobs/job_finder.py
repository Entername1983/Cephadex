
from sqlalchemy import select
from models.models_ import JobNotification, Job
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class JobFinder():
    @staticmethod
    async def find_pending_jobs(session: 'AsyncSession') -> list[Job]:
        result = await session.execute(select(Job).filter_by(state="queued"))
        return result.scalars().all()
    
    @staticmethod
    async def find_pending_notifications(session: 'AsyncSession') -> 'JobNotification':
        result = await session.execute(select(JobNotification).filter_by(state="queued"))
        return result.scalars_one()
    
    @staticmethod
    async def find_pending_notification(session: 'AsyncSession', slug: str) -> 'JobNotification':
        result = await session.execute(select(JobNotification).filter_by(state="queued", slug=slug))
        return result.scalar_one()