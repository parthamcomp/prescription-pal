import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_issued_before_password_change,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models_db import User
from app.repositories import users as users_repo
from app.schemas import (
    CONSENT_VERSION,
    LoginRequest,
    OkResponse,
    RefreshRequest,
    RegisterRequest,
    UserOut,
)
from app.services.rate_limit import ip_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = "/api/auth"

_GENERIC_REGISTER_ERROR = "Could not register with the details provided."


def _set_auth_cookies(response: Response, user: User) -> None:
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
    # Tokens live only in HttpOnly cookies now - returning them in the JSON
    # body too would hand a script-readable copy to anything that can read
    # the response (XSS, overly-broad logging), defeating the point of
    # HttpOnly. The frontend never reads them from the body (it calls
    # /api/auth/me separately), so there was nothing relying on this.


@router.post(
    "/register",
    response_model=OkResponse,
    dependencies=[Depends(ip_rate_limit(5, 3600, "register"))],
)
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
        # Same generic failure as a bad login - do not reveal whether the
        # email is already registered. The hash below costs roughly the same
        # as the real create_user() path so the two branches don't diverge
        # in timing either.
        hash_password(body.password)
        raise HTTPException(status_code=400, detail=_GENERIC_REGISTER_ERROR)
    user = await users_repo.create_user(
        db,
        body.email,
        body.password,
        body.display_name,
        consent_version=CONSENT_VERSION,
    )
    _set_auth_cookies(response, user)
    return OkResponse()


@router.post(
    "/login",
    response_model=OkResponse,
    dependencies=[Depends(ip_rate_limit(10, 300, "login"))],
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await users_repo.get_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _set_auth_cookies(response, user)
    return OkResponse()


@router.post(
    "/refresh",
    response_model=OkResponse,
    dependencies=[Depends(ip_rate_limit(30, 300, "refresh"))],
)
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
    if token_issued_before_password_change(payload, user.password_changed_at):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    _set_auth_cookies(response, user)
    return OkResponse()


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
