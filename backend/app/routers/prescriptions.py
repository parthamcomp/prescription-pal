import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import children as children_repo
from app.repositories import jobs as jobs_repo
from app.repositories import prescriptions as repo
from app.schemas import PrescriptionCreate, PrescriptionOut
from app.services.embeddings import embed_text
from app.services.objects import presigned_url
from app.services.rag import build_document

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


async def _document_and_embedding(data: PrescriptionCreate):
    document = build_document(data)
    try:
        embedding = await embed_text(document)
    except Exception:  # noqa: BLE001
        embedding = None
    return document, embedding


async def _require_owned_child(
    db: AsyncSession, owner_id: uuid.UUID, child_id: uuid.UUID
) -> None:
    # child_id is a bare UUID at the Pydantic level - nothing there confirms
    # it's actually one of this account's children rather than, say, another
    # user's. Records now drive real behavior off that ownership (cascade
    # delete when the child is removed), so an unchecked id would let a
    # request attach a record to a child it has no access to.
    if await children_repo.get_for_user(db, owner_id, child_id) is None:
        raise HTTPException(status_code=400, detail="Child not found")


@router.get("", response_model=list[PrescriptionOut])
async def list_prescriptions(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    child_id: uuid.UUID | None = Query(None),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_for_user(
        db, owner_id, limit=limit, offset=offset, child_id=child_id
    )


@router.get("/{prescription_id}", response_model=PrescriptionOut)
async def get_prescription(
    prescription_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    model = await repo.get_for_user(db, owner_id, prescription_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return model


@router.post("", response_model=PrescriptionOut)
async def create_prescription(
    body: PrescriptionCreate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_owned_child(db, owner_id, body.child_id)

    image_keys: list[str] = []
    if body.source_job_id is not None:
        job = await jobs_repo.get_for_user(db, owner_id, body.source_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload not found")
        image_keys = job.image_keys or []

    document, embedding = await _document_and_embedding(body)
    prescription = await repo.create_for_user(
        db, owner_id, body, document, embedding, image_keys=image_keys
    )

    if body.source_job_id is not None:
        await jobs_repo.mark_saved(db, job)

    return prescription


@router.put("/{prescription_id}", response_model=PrescriptionOut)
async def update_prescription(
    prescription_id: uuid.UUID,
    body: PrescriptionCreate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_owned_child(db, owner_id, body.child_id)

    document, embedding = await _document_and_embedding(body)
    model = await repo.update_for_user(
        db, owner_id, prescription_id, body, document, embedding
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return model


@router.get("/{prescription_id}/photos", response_model=list[str])
async def get_prescription_photos(
    prescription_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    model = await repo.get_for_user(db, owner_id, prescription_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return [
        await run_in_threadpool(presigned_url, key) for key in model.image_keys or []
    ]


@router.delete("/{prescription_id}")
async def delete_prescription(
    prescription_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    if not await repo.delete_for_user(db, owner_id, prescription_id):
        raise HTTPException(status_code=404, detail="Prescription not found")
    return {"deleted": True}
