from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def _create_token(subject: str, expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject, timedelta(minutes=settings.access_ttl_min), "access"
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, timedelta(days=settings.refresh_ttl_days), "refresh"
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])


def token_issued_before_password_change(payload: dict, password_changed_at) -> bool:
    """True if a token was signed before the user's most recent password
    change - i.e. it was issued under a credential that's no longer valid
    and should be rejected even though its own signature/expiry still check
    out. Without this, changing your password does not invalidate tokens an
    attacker (or an old device) already holds."""
    if password_changed_at is None:
        return False
    iat = payload.get("iat")
    if iat is None:
        return True
    issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
    # JWT iat is whole seconds (jose truncates when encoding); Postgres
    # keeps microseconds on password_changed_at. Compared at full precision,
    # a token issued in the same wall-clock second as the password change
    # (e.g. the login that immediately follows changing it) can truncate to
    # "before" a changed_at that has non-zero microseconds, wrongly
    # invalidating a session that was never actually stale. Compare at
    # second granularity on both sides to match iat's actual precision.
    return issued_at < password_changed_at.replace(microsecond=0)
