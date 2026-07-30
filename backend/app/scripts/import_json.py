"""Import the legacy data/prescriptions.json into Postgres under one account.

Usage (inside the backend container):
    python -m app.scripts.import_json <email> <password> [path/to/prescriptions.json]
"""
import asyncio
import json
import sys
from pathlib import Path

from app.db import SessionLocal
from app.repositories import prescriptions as repo
from app.repositories import users as users_repo
from app.schemas import PrescriptionCreate
from app.services.embeddings import embed_text
from app.services.rag import build_document


async def main(email: str, password: str, path: str) -> None:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    async with SessionLocal() as db:
        user = await users_repo.get_by_email(db, email)
        if user is None:
            user = await users_repo.create_user(db, email, password, "")
            print(f"Created user {email}")

        allowed = set(PrescriptionCreate.model_fields.keys())
        imported = 0
        for rec in records:
            payload = {k: v for k, v in rec.items() if k in allowed}
            data = PrescriptionCreate(**payload)
            document = build_document(data)
            try:
                embedding = await embed_text(document)
            except Exception:  # noqa: BLE001
                embedding = None
            await repo.create_for_user(db, user.id, data, document, embedding)
            imported += 1

        print(f"Imported {imported} prescriptions for {email}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m app.scripts.import_json <email> <password> [path]")
        raise SystemExit(1)
    _email = sys.argv[1]
    _password = sys.argv[2]
    _path = sys.argv[3] if len(sys.argv) > 3 else "data/prescriptions.json"
    asyncio.run(main(_email, _password, _path))
