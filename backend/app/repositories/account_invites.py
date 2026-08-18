import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import AccountInvite


async def create_invite(
    db: AsyncSession, owner_user_id: uuid.UUID, token: str, expires_at: datetime
) -> AccountInvite:
    invite = AccountInvite(
        owner_user_id=owner_user_id, token=token, expires_at=expires_at
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def get_valid_by_token(db: AsyncSession, token: str) -> AccountInvite | None:
    result = await db.execute(
        select(AccountInvite).where(AccountInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        return None
    if invite.accepted_at is not None:
        return None
    if invite.expires_at < datetime.now(timezone.utc):
        return None
    return invite


async def mark_accepted(db: AsyncSession, invite: AccountInvite) -> None:
    invite.accepted_at = datetime.now(timezone.utc)
    await db.commit()
