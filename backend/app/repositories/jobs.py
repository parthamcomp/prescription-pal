import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import ProcessingJob


async def create_job(
    db: AsyncSession, user_id: uuid.UUID, image_keys: list[str]
) -> ProcessingJob:
    job = ProcessingJob(user_id=user_id, image_keys=image_keys, status="queued")
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[ProcessingJob]:
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.user_id == user_id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_for_user(
    db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> ProcessingJob | None:
    result = await db.execute(
        select(ProcessingJob).where(
            ProcessingJob.id == job_id,
            ProcessingJob.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, job_id: uuid.UUID) -> ProcessingJob | None:
    return await db.get(ProcessingJob, job_id)


async def update_status(
    db: AsyncSession,
    job: ProcessingJob,
    status: str,
    *,
    raw_text: str | None = None,
    extracted: dict | None = None,
    error: str | None = None,
) -> ProcessingJob:
    job.status = status
    if raw_text is not None:
        job.raw_text = raw_text
    if extracted is not None:
        job.extracted = extracted
    if error is not None:
        job.error = error
    await db.commit()
    await db.refresh(job)
    return job


async def mark_saved(db: AsyncSession, job: ProcessingJob) -> None:
    job.saved = True
    await db.commit()
