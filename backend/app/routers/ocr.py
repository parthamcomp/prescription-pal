import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import get_current_user
from app.config import settings
from app.db import get_db
from app.models_db import User
from app.queue import get_pool
from app.repositories import jobs as jobs_repo
from app.schemas import JobCreated
from app.services.objects import put_object

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("", response_model=JobCreated)
async def submit_ocr(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file (JPEG, PNG, etc.)")

    image_bytes = await file.read()
    if len(image_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail=f"Image must be under {settings.max_upload_mb} MB"
        )

    image_key = f"uploads/{user.id}/{uuid.uuid4()}"
    await run_in_threadpool(put_object, image_key, image_bytes, file.content_type)

    job = await jobs_repo.create_job(db, user.id, image_key)

    pool = await get_pool()
    await pool.enqueue_job("process_ocr_job", str(job.id))

    return JobCreated(job_id=job.id, status=job.status)
