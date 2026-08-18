import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import jobs as jobs_repo
from app.schemas import JobOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    return await jobs_repo.list_for_user(db, owner_id, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    job = await jobs_repo.get_for_user(db, owner_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
