import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_data_owner_id
from app.db import get_db
from app.repositories import children as children_repo
from app.repositories import jobs as jobs_repo
from app.repositories import measurements as repo
from app.routers.deps import require_owned_child
from app.schemas import (
    ChildSex,
    MeasurementCreate,
    MeasurementOut,
    PercentileCurvesOut,
)
from app.services import growth
from app.services.units import height_to_cm, weight_to_kg

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


async def _to_out(db: AsyncSession, m) -> MeasurementOut:
    child = await children_repo.get_for_user(db, m.user_id, m.child_id)
    age_months = None
    height_pct = None
    weight_pct = None
    if child and child.date_of_birth:
        age_months = round(growth.age_in_months(child.date_of_birth, m.measured_on), 1)
        if child.sex and growth.in_supported_range(age_months):
            if m.height_cm is not None:
                height_pct = growth.percentile_for_value(
                    "height_for_age", child.sex, age_months, m.height_cm
                )
            if m.weight_kg is not None:
                weight_pct = growth.percentile_for_value(
                    "weight_for_age", child.sex, age_months, m.weight_kg
                )
    return MeasurementOut(
        id=m.id,
        child_id=m.child_id,
        measured_on=m.measured_on,
        height_cm=m.height_cm,
        weight_kg=m.weight_kg,
        source=m.source,
        age_months=age_months,
        height_percentile=height_pct,
        weight_percentile=weight_pct,
    )


@router.get("", response_model=list[MeasurementOut])
async def list_measurements(
    child_id: uuid.UUID = Query(...),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    await require_owned_child(db, owner_id, child_id)
    rows = await repo.list_for_user(db, owner_id, child_id)
    return [await _to_out(db, m) for m in rows]


@router.post("", response_model=MeasurementOut)
async def create_measurement(
    body: MeasurementCreate,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    await require_owned_child(db, owner_id, body.child_id)

    image_keys: list[str] = []
    job = None
    if body.source_job_id is not None:
        job = await jobs_repo.get_for_user(db, owner_id, body.source_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload not found")
        image_keys = job.image_keys or []

    m = await repo.create_for_user(
        db,
        owner_id,
        body.child_id,
        body.measured_on,
        height_to_cm(body.height_value, body.height_unit),
        weight_to_kg(body.weight_value, body.weight_unit),
        body.source,
        image_keys,
    )

    if job is not None:
        # Fires from either save path (this one or prescriptions') when a
        # source_job_id is present - otherwise a photo saved only as a
        # measurement (no prescription text worth keeping) stays stuck in
        # "pending uploads" forever.
        await jobs_repo.mark_saved(db, job)

    return await _to_out(db, m)


@router.delete("/{measurement_id}")
async def delete_measurement(
    measurement_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    if not await repo.delete_for_user(db, owner_id, measurement_id):
        raise HTTPException(status_code=404, detail="Measurement not found")
    return {"deleted": True}


@router.get("/percentile-curves", response_model=PercentileCurvesOut)
async def percentile_curves(sex: ChildSex = Query(...)):
    return PercentileCurvesOut(
        height_for_age=growth.percentile_curves("height_for_age", sex),
        weight_for_age=growth.percentile_curves("weight_for_age", sex),
    )
