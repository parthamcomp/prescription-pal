import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models_db import User
from app.repositories import prescriptions as repo
from app.schemas import PrescriptionCreate, PrescriptionOut
from app.services.embeddings import embed_text
from app.services.rag import build_document

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])


async def _document_and_embedding(data: PrescriptionCreate):
    document = build_document(data)
    try:
        embedding = await embed_text(document)
    except Exception:  # noqa: BLE001
        embedding = None
    return document, embedding


@router.get("", response_model=list[PrescriptionOut])
async def list_prescriptions(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    child_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_for_user(
        db, user.id, limit=limit, offset=offset, child_id=child_id
    )


@router.get("/{prescription_id}", response_model=PrescriptionOut)
async def get_prescription(
    prescription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    model = await repo.get_for_user(db, user.id, prescription_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return model


@router.post("", response_model=PrescriptionOut)
async def create_prescription(
    body: PrescriptionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document, embedding = await _document_and_embedding(body)
    return await repo.create_for_user(db, user.id, body, document, embedding)


@router.put("/{prescription_id}", response_model=PrescriptionOut)
async def update_prescription(
    prescription_id: uuid.UUID,
    body: PrescriptionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document, embedding = await _document_and_embedding(body)
    model = await repo.update_for_user(
        db, user.id, prescription_id, body, document, embedding
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Prescription not found")
    return model


@router.delete("/{prescription_id}")
async def delete_prescription(
    prescription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await repo.delete_for_user(db, user.id, prescription_id):
        raise HTTPException(status_code=404, detail="Prescription not found")
    return {"deleted": True}
