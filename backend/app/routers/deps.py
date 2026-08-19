import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import children as children_repo


async def require_owned_child(
    db: AsyncSession, owner_id: uuid.UUID, child_id: uuid.UUID
) -> None:
    # A bare UUID at the Pydantic level doesn't confirm it's actually one of
    # this account's children rather than someone else's - every router that
    # attaches a row to a child_id needs this check before writing.
    if await children_repo.get_for_user(db, owner_id, child_id) is None:
        raise HTTPException(status_code=400, detail="Child not found")
