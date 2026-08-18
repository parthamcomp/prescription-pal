import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import children as repo
from app.schemas import ChildCreate, ChildOut, ChildUpdate

router = APIRouter(prefix="/api/children", tags=["children"])

_DUPLICATE_NAME_ERROR = "A child with that name already exists on this account."


@router.get("", response_model=list[ChildOut])
async def list_children(
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    return await repo.list_for_user(db, owner_id)


@router.get("/{child_id}", response_model=ChildOut)
async def get_child(
    child_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    child = await repo.get_for_user(db, owner_id, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.post("", response_model=ChildOut)
async def create_child(
    body: ChildCreate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await repo.create_for_user(db, owner_id, body.name, body.date_of_birth)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=_DUPLICATE_NAME_ERROR)


@router.patch("/{child_id}", response_model=ChildOut)
async def update_child(
    child_id: uuid.UUID,
    body: ChildUpdate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        child = await repo.update_for_user(
            db, owner_id, child_id, body.name, body.date_of_birth
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=_DUPLICATE_NAME_ERROR)
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.delete("/{child_id}")
async def delete_child(
    child_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    if not await repo.delete_for_user(db, owner_id, child_id):
        raise HTTPException(status_code=404, detail="Child not found")
    return {"deleted": True}
