import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import prescriptions as repo
from app.schemas import MedOut
from app.services.meds import derive_medications

router = APIRouter(prefix="/api/medications", tags=["medications"])


@router.get("", response_model=list[MedOut])
async def list_medications(
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    prescriptions = await repo.list_for_user(db, owner_id, limit=500)
    return derive_medications(prescriptions)
