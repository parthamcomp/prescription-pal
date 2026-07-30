import asyncio
import uuid

from app.db import SessionLocal
from app.queue import redis_settings as _redis_settings
from app.repositories import jobs as jobs_repo
from app.services.extraction import extract_prescription_from_text
from app.services.objects import ensure_bucket, get_object
from app.services.ocr import extract_text_from_image


async def process_ocr_job(ctx, job_id: str) -> dict:
    """Arq task: OCR an uploaded image, then extract structured fields."""
    jid = uuid.UUID(job_id)
    async with SessionLocal() as db:
        job = await jobs_repo.get_by_id(db, jid)
        if job is None:
            return {"error": "job not found"}

        await jobs_repo.update_status(db, job, "processing")
        try:
            image_bytes = await asyncio.to_thread(get_object, job.image_key)
            raw_text = await asyncio.to_thread(extract_text_from_image, image_bytes)
            if not raw_text:
                await jobs_repo.update_status(
                    db,
                    job,
                    "error",
                    error="No text detected. Try a clearer photo with good lighting.",
                )
                return {"status": "error"}

            extracted = await extract_prescription_from_text(raw_text)
            await jobs_repo.update_status(
                db, job, "done", raw_text=raw_text, extracted=extracted
            )
            return {"status": "done"}
        except Exception as exc:  # noqa: BLE001
            await jobs_repo.update_status(db, job, "error", error=str(exc))
            return {"status": "error", "detail": str(exc)}


async def startup(ctx) -> None:
    try:
        ensure_bucket()
    except Exception:  # noqa: BLE001
        pass


class WorkerSettings:
    functions = [process_ocr_job]
    on_startup = startup
    redis_settings = _redis_settings()
