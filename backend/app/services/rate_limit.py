import time

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.auth.deps import get_current_user
from app.config import settings
from app.models_db import User

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def _check(name: str, identity: str, limit: int, window_seconds: int) -> None:
    # Fixed window keyed by name+identity+window index - shared via Redis so
    # the limit holds across multiple API instances, not just in-process.
    window = int(time.time()) // window_seconds
    key = f"ratelimit:{name}:{identity}:{window}"
    try:
        r = _client()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
    except Exception:  # noqa: BLE001 - a rate-limiter outage must not take the API down
        return
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again shortly.",
        )


def ip_rate_limit(limit: int, window_seconds: int, name: str):
    """Dependency factory: limits requests per client IP. Use for
    unauthenticated endpoints (login/register/refresh) where there is no
    user identity yet to key on."""

    async def dependency(request: Request) -> None:
        identity = request.client.host if request.client else "unknown"
        await _check(name, identity, limit, window_seconds)

    return dependency


def user_rate_limit(limit: int, window_seconds: int, name: str):
    """Dependency factory: limits requests per authenticated user. Depends on
    get_current_user itself so FastAPI resolves/caches the user once per
    request rather than duplicating auth work."""

    async def dependency(user: User = Depends(get_current_user)) -> None:
        await _check(name, str(user.id), limit, window_seconds)

    return dependency
