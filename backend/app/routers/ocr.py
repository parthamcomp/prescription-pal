import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import get_data_owner_id
from app.config import settings
from app.db import get_db
from app.queue import get_pool
from app.repositories import jobs as jobs_repo
from app.schemas import JobCreated
from app.services.objects import put_object
from app.services.rate_limit import user_rate_limit

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


MAX_PAGES = 6


@router.post(
    "",
    response_model=JobCreated,
    dependencies=[Depends(user_rate_limit(20, 3600, "ocr"))],
)
async def submit_ocr(
    files: list[UploadFile] = File(...),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one image file")
    if len(files) > MAX_PAGES:
        raise HTTPException(
            status_code=400, detail=f"Upload at most {MAX_PAGES} pages at a time"
        )

    image_keys: list[str] = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="Upload an image file (JPEG, PNG, etc.)"
            )
        image_bytes = await file.read()
        if len(image_bytes) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Each image must be under {settings.max_upload_mb} MB",
            )
        image_key = f"uploads/{owner_id}/{uuid.uuid4()}"
        await run_in_threadpool(put_object, image_key, image_bytes, file.content_type)
        image_keys.append(image_key)

    job = await jobs_repo.create_job(db, owner_id, image_keys)

    pool = await get_pool()
    await pool.enqueue_job("process_ocr_job", str(job.id))

    return JobCreated(job_id=job.id, status=job.status)
