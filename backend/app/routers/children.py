from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models_db import User
from app.repositories import children as repo
from app.schemas import ChildCreate, ChildOut

router = APIRouter(prefix="/api/children", tags=["children"])


@router.get("", response_model=list[ChildOut])
async def list_children(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_for_user(db, user.id)


@router.post("", response_model=ChildOut)
async def create_child(
    body: ChildCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await repo.create_for_user(db, user.id, body.name, body.date_of_birth)
