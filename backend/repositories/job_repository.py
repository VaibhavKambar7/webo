from typing import List, Optional
from sqlalchemy.future import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.sql_models import Job


class JobRepository:
    async def create(self, job_data: dict) -> Job:
        """handles only db operations for job entity."""

        async with AsyncSessionLocal() as session:
            db_job = Job(**job_data)
            session.add(db_job)
            await session.commit()
            await session.refresh(db_job)
            return db_job

    async def get_by_id(self, job_id: str) -> Optional[Job]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Job).filter(Job.job_id == job_id))
            return result.scalars().first()

    async def get_by_chat_id(self, chat_id: str) -> List[Job]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job)
                .filter(Job.chat_id == chat_id)
                .order_by(Job.created_at.asc())
            )
            return result.scalars().all()

    async def update(self, job_id: str, updates: dict) -> Optional[Job]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Job).filter(Job.job_id == job_id))
            job = result.scalars().first()

            if job:
                for key, value in updates.items():
                    setattr(job, key, value)
                await session.commit()
                await session.refresh(job)

            return job
