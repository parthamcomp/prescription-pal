"""Shared-account membership: a member has full symmetric access to the
data owned by whoever invited them. member_user_id is unique - a user can
be a member of at most one shared account at a time."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_db import AccountLink, User


async def get_link_for_member(
    db: AsyncSession, member_user_id: uuid.UUID
) -> AccountLink | None:
    result = await db.execute(
        select(AccountLink).where(AccountLink.member_user_id == member_user_id)
    )
    return result.scalar_one_or_none()


async def list_members(db: AsyncSession, owner_user_id: uuid.UUID) -> list[User]:
    result = await db.execute(
        select(User)
        .join(AccountLink, AccountLink.member_user_id == User.id)
        .where(AccountLink.owner_user_id == owner_user_id)
        .order_by(AccountLink.created_at)
    )
    return list(result.scalars().all())


async def has_members(db: AsyncSession, owner_user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(AccountLink.id).where(AccountLink.owner_user_id == owner_user_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def create_link(
    db: AsyncSession, owner_user_id: uuid.UUID, member_user_id: uuid.UUID
) -> AccountLink:
    link = AccountLink(owner_user_id=owner_user_id, member_user_id=member_user_id)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def remove_member(
    db: AsyncSession, owner_user_id: uuid.UUID, member_user_id: uuid.UUID
) -> bool:
    link = await get_link_for_member(db, member_user_id)
    if link is None or link.owner_user_id != owner_user_id:
        return False
    await db.delete(link)
    await db.commit()
    return True


async def remove_self(db: AsyncSession, member_user_id: uuid.UUID) -> bool:
    link = await get_link_for_member(db, member_user_id)
    if link is None:
        return False
    await db.delete(link)
    await db.commit()
    return True
