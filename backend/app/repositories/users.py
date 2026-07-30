from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.models_db import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: str = "",
    *,
    consent_version: str | None = None,
) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        display_name=display_name,
        consent_accepted_at=datetime.now(timezone.utc) if consent_version else None,
        consent_version=consent_version,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_display_name(db: AsyncSession, user: User, display_name: str) -> User:
    user.display_name = display_name
    await db.commit()
    await db.refresh(user)
    return user


async def update_password(db: AsyncSession, user: User, password_hash: str) -> User:
    user.password_hash = password_hash
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.commit()
