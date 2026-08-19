"""CRUD for vaccination doses, always scoped to the owning user. A row's
existence means "given" - see the 0010_vaccination_doses migration docstring.
"""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import VaccinationDose


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID
) -> list[VaccinationDose]:
    result = await db.execute(
        select(VaccinationDose).where(
            VaccinationDose.user_id == user_id, VaccinationDose.child_id == child_id
        )
    )
    return list(result.scalars().all())


async def upsert_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    child_id: uuid.UUID,
    scheduled_slug: str,
    date_administered: date,
) -> VaccinationDose:
    result = await db.execute(
        select(VaccinationDose).where(
            VaccinationDose.user_id == user_id,
            VaccinationDose.child_id == child_id,
            VaccinationDose.scheduled_slug == scheduled_slug,
        )
    )
    dose = result.scalar_one_or_none()
    if dose is None:
        dose = VaccinationDose(
            user_id=user_id,
            child_id=child_id,
            scheduled_slug=scheduled_slug,
            date_administered=date_administered,
        )
        db.add(dose)
    else:
        dose.date_administered = date_administered
    await db.commit()
    await db.refresh(dose)
    return dose


async def delete_for_user(
    db: AsyncSession, user_id: uuid.UUID, child_id: uuid.UUID, scheduled_slug: str
) -> bool:
    result = await db.execute(
        select(VaccinationDose).where(
            VaccinationDose.user_id == user_id,
            VaccinationDose.child_id == child_id,
            VaccinationDose.scheduled_slug == scheduled_slug,
        )
    )
    dose = result.scalar_one_or_none()
    if dose is None:
        return False
    await db.delete(dose)
    await db.commit()
    return True
