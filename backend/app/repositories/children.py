"""CRUD for child profiles, always scoped to the owning user."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import Child


async def list_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Child]:
    result = await db.execute(
        select(Child).where(Child.user_id == user_id).order_by(Child.name)
    )
    return list(result.scalars().all())


async def get_for_user(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> Child | None:
    result = await db.execute(
        select(Child).where(Child.id == child_id, Child.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    date_of_birth: date | None,
) -> Child:
    child = Child(user_id=user_id, name=name, date_of_birth=date_of_birth)
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


async def update_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    child_id: uuid.UUID,
    name: str,
    date_of_birth: date | None,
) -> Child | None:
    child = await get_for_user(db, user_id, child_id)
    if child is None:
        return None
    child.name = name
    child.date_of_birth = date_of_birth
    await db.commit()
    await db.refresh(child)
    return child


async def delete_for_user(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> bool:
    child = await get_for_user(db, user_id, child_id)
    if child is None:
        return False
    await db.delete(child)
    await db.commit()
    return True
