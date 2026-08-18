import uuid

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_token, token_issued_before_password_change
from app.db import get_db
from app.models_db import User
from app.repositories import account_links as account_links_repo

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_token(request: Request) -> str | None:
    """Prefer the HttpOnly cookie; fall back to a Bearer header for API clients."""
    token = request.cookies.get("access_token")
    if token:
        return token
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_token(request)
    if not token:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise _CREDENTIALS_ERROR
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise _CREDENTIALS_ERROR

    user = await db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    if token_issued_before_password_change(payload, user.password_changed_at):
        raise _CREDENTIALS_ERROR
    return user


async def get_data_owner_id(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Resolves which user's data (children, prescriptions, chat, uploads)
    the current login should act against - their own, or the account
    they've been given shared access to as a member. Use this everywhere a
    data route currently scopes by `user.id`; keep using `user.id` directly
    for identity-only operations (profile, password, account deletion)."""
    link = await account_links_repo.get_link_for_member(db, user.id)
    return link.owner_user_id if link else user.id
