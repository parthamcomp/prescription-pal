"""Import the legacy data/prescriptions.json into Postgres under one account.

Usage (inside the backend container):
    python -m app.scripts.import_json <email> <password> <child name> [path/to/prescriptions.json]

The legacy JSON predates the Child model, so every imported record is
assigned to one child (created if they don't already exist under this
account) - PrescriptionCreate.child_id is required, since the API no longer
accepts unassigned records.
"""
import asyncio
import json
import sys
from pathlib import Path

from app.db import SessionLocal
from app.repositories import children as children_repo
from app.repositories import prescriptions as repo
from app.repositories import users as users_repo
from app.schemas import PrescriptionCreate
from app.services.embeddings import embed_text
from app.services.rag import build_document


async def main(email: str, password: str, child_name: str, path: str) -> None:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    async with SessionLocal() as db:
        user = await users_repo.get_by_email(db, email)
        if user is None:
            user = await users_repo.create_user(db, email, password, "")
            print(f"Created user {email}")

        child = next(
            (c for c in await children_repo.list_for_user(db, user.id) if c.name == child_name),
            None,
        )
        if child is None:
            child = await children_repo.create_for_user(db, user.id, child_name, None)
            print(f"Created child {child_name}")

        allowed = set(PrescriptionCreate.model_fields.keys()) - {"child_id"}
        imported = 0
        for rec in records:
            payload = {k: v for k, v in rec.items() if k in allowed}
            data = PrescriptionCreate(**payload, child_id=child.id)
            document = build_document(data)
            try:
                embedding = await embed_text(document)
            except Exception:  # noqa: BLE001
                embedding = None
            await repo.create_for_user(db, user.id, data, document, embedding)
            imported += 1

        print(f"Imported {imported} prescriptions for {email}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python -m app.scripts.import_json <email> <password> <child name> [path]"
        )
        raise SystemExit(1)
    _email = sys.argv[1]
    _password = sys.argv[2]
    _child_name = sys.argv[3]
    _path = sys.argv[4] if len(sys.argv) > 4 else "data/prescriptions.json"
    asyncio.run(main(_email, _password, _child_name, _path))
