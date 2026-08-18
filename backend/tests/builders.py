"""Test data builders: plain functions with sensible defaults and explicit
overrides, not shared fixture files or factory_boy.

factory_boy's SQLAlchemy integration assumes a sync Session; this codebase
is async top to bottom, so the ORM-backed builders below just take the
async session directly and await the insert themselves - simpler than
fighting factory_boy's session-binding model for one extra dependency.
"""
import uuid
from datetime import date

from app.auth.security import hash_password
from app.models_db import AccountInvite, AccountLink, Child, Prescription, ProcessingJob, User


def medication(**overrides) -> dict:
    data = {
        "name": "Amoxicillin",
        "form": "Syrup",
        "dosage": "250mg/5ml",
        "frequency": "twice daily",
        "duration": "7 days",
    }
    data.update(overrides)
    return data


def prescription_payload(**overrides) -> dict:
    """A dict matching PrescriptionCreate - handy for both schema
    validation tests and POST /api/prescriptions request bodies.

    child_id has no default - PrescriptionCreate requires a real one (the
    router also checks it belongs to the caller's account), so callers must
    pass an id from a child created via make_child() in the same test."""
    data = {
        "doctor_name": "Dr. Patel",
        "date_of_visit": "2026-06-01",
        "complaint": "cough",
        "diagnosis": "common cold",
        "medications": [medication()],
        "child_age": "4 years",
        "child_weight": "16kg",
        "additional_notes": "",
    }
    data.update(overrides)
    return data


async def make_user(db, **overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
        "password_hash": hash_password("Str0ng!Passw0rd"),
        "display_name": "Test User",
    }
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_child(db, user_id: uuid.UUID, **overrides) -> Child:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "name": f"Kid-{uuid.uuid4().hex[:6]}",
        "date_of_birth": date(2020, 1, 1),
    }
    defaults.update(overrides)
    child = Child(**defaults)
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return child


async def make_prescription(db, user_id: uuid.UUID, **overrides) -> Prescription:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "doctor_name": "Dr. Patel",
        "date_of_visit": date(2026, 6, 1),
        "complaint": "cough",
        "diagnosis": "common cold",
        "medications": [medication()],
        "child_age": "4 years",
        "child_weight": "16kg",
        "additional_notes": "",
        "document": "stub document",
        "image_keys": [],
    }
    defaults.update(overrides)
    prescription = Prescription(**defaults)
    db.add(prescription)
    await db.commit()
    await db.refresh(prescription)
    return prescription


async def make_job(db, user_id: uuid.UUID, **overrides) -> ProcessingJob:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "status": "queued",
        "image_keys": [],
    }
    defaults.update(overrides)
    job = ProcessingJob(**defaults)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def make_account_link(db, owner_user_id: uuid.UUID, member_user_id: uuid.UUID, **overrides) -> AccountLink:
    defaults = {"id": uuid.uuid4(), "owner_user_id": owner_user_id, "member_user_id": member_user_id}
    defaults.update(overrides)
    link = AccountLink(**defaults)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def make_invite(db, owner_user_id: uuid.UUID, **overrides) -> AccountInvite:
    from datetime import datetime, timedelta, timezone

    defaults = {
        "id": uuid.uuid4(),
        "owner_user_id": owner_user_id,
        "token": uuid.uuid4().hex,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }
    defaults.update(overrides)
    invite = AccountInvite(**defaults)
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite
