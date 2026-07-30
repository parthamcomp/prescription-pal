import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models_db import User
from app.repositories import users as users_repo
from app.schemas import (
    CONSENT_VERSION,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = "/api/auth"


def _set_auth_cookies(response: Response, user: User) -> TokenResponse:
    subject = str(user.id)
    access = create_access_token(subject)
    refresh = create_refresh_token(subject)
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain

    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_ttl_min * 60,
        path="/",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_ttl_days * 86400,
        path=REFRESH_PATH,
        **common,
    )
    # Tokens are also returned in the body for non-browser API clients.
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="You must accept that this app repeats your prescription "
            "records and does not give medical advice.",
        )
    existing = await users_repo.get_by_email(db, body.email)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await users_repo.create_user(
        db,
        body.email,
        body.password,
        body.display_name,
        consent_version=CONSENT_VERSION,
    )
    return _set_auth_cookies(response, user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await users_repo.get_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _set_auth_cookies(response, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    token = request.cookies.get(REFRESH_COOKIE) or (
        body.refresh_token if body else None
    )
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _set_auth_cookies(response, user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
