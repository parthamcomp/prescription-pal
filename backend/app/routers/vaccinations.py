import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import children as children_repo
from app.repositories import vaccination_doses as repo
from app.routers.deps import require_owned_child
from app.schemas import ScheduleStatusOut, VaccinationDoseCreate
from app.services.vaccination_schedule import compute_status, load_schedule

router = APIRouter(prefix="/api/vaccinations", tags=["vaccinations"])

_KNOWN_SLUGS = {
    v["slug"] for m in load_schedule()["milestones"] for v in m["vaccines"]
}


@router.get("/schedule-status", response_model=ScheduleStatusOut)
async def schedule_status(
    child_id: uuid.UUID = Query(...),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    child = await children_repo.get_for_user(db, owner_id, child_id)
    if child is None:
        raise HTTPException(status_code=404, detail="Child not found")
    doses = await repo.list_for_user(db, owner_id, child_id)
    return compute_status(doses, child.date_of_birth, date.today())


@router.post("/doses")
async def upsert_dose(
    body: VaccinationDoseCreate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    await require_owned_child(db, owner_id, body.child_id)
    if body.scheduled_slug not in _KNOWN_SLUGS:
        raise HTTPException(status_code=400, detail="Unknown vaccine")
    if body.date_administered > date.today():
        raise HTTPException(status_code=400, detail="Date can't be in the future")
    child = await children_repo.get_for_user(db, owner_id, body.child_id)
    if child.date_of_birth and body.date_administered < child.date_of_birth:
        raise HTTPException(
            status_code=400, detail="Date can't be before the child's date of birth"
        )
    dose = await repo.upsert_for_user(
        db, owner_id, body.child_id, body.scheduled_slug, body.date_administered
    )
    return {"scheduled_slug": dose.scheduled_slug, "date_administered": dose.date_administered}


@router.delete("/doses/{child_id}/{scheduled_slug}")
async def delete_dose(
    child_id: uuid.UUID,
    scheduled_slug: str,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    if not await repo.delete_for_user(db, owner_id, child_id, scheduled_slug):
        raise HTTPException(status_code=404, detail="Dose not found")
    return {"deleted": True}
