from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models_db import User
from app.repositories import prescriptions as repo
from app.schemas import MedOut
from app.services.meds import derive_medications

router = APIRouter(prefix="/api/medications", tags=["medications"])


@router.get("", response_model=list[MedOut])
async def list_medications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prescriptions = await repo.list_for_user(db, user.id, limit=500)
    return derive_medications(prescriptions)
