"""CRUD for growth measurements, always scoped to the owning user."""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import Measurement


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> list[Measurement]:
    result = await db.execute(
        select(Measurement)
        .where(Measurement.user_id == user_id, Measurement.child_id == child_id)
        .order_by(Measurement.measured_on.desc())
    )
    return list(result.scalars().all())


async def get_for_user(
    db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID
) -> Measurement | None:
    result = await db.execute(
        select(Measurement).where(
            Measurement.id == measurement_id, Measurement.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def create_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    child_id: uuid.UUID,
    measured_on: date,
    height_cm: float | None,
    weight_kg: float | None,
    source: str,
    image_keys: list[str],
) -> Measurement:
    m = Measurement(
        user_id=user_id,
        child_id=child_id,
        measured_on=measured_on,
        height_cm=height_cm,
        weight_kg=weight_kg,
        source=source,
        image_keys=image_keys,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def delete_for_user(
    db: AsyncSession, user_id: uuid.UUID, measurement_id: uuid.UUID
) -> bool:
    m = await get_for_user(db, user_id, measurement_id)
    if m is None:
        return False
    await db.delete(m)
    await db.commit()
    return True
