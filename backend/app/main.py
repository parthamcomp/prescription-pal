from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth.deps import get_current_user
from app.config import settings
from app.logging_conf import setup_logging
from app.metrics import metrics
from app.models_db import User
from app.queue import close_pool
from app.routers import (
    account,
    auth,
    chat,
    children,
    household,
    jobs,
    measurements,
    medications,
    ocr,
    prescriptions,
    vaccinations,
)
from app.services.budget import budget
from app.services.objects import ensure_bucket

logger = setup_logging()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains"
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_bucket()
    except Exception:  # noqa: BLE001
        pass
    logger.info("startup_complete")
    yield
    await close_pool()


app = FastAPI(
    title="Medical Prescription Assistant",
    description="Multi-user prescription knowledge base with OCR and chat",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Transport security. Off by default so local dev works over plain HTTP;
# enable ENFORCE_HTTPS=true in production (behind the platform's TLS).
if settings.enforce_https:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HTTPSRedirectMiddleware)
if settings.trusted_hosts_list and settings.trusted_hosts_list != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list
    )

app.include_router(auth.router)
app.include_router(children.router)
app.include_router(prescriptions.router)
app.include_router(chat.router)
app.include_router(ocr.router)
app.include_router(jobs.router)
app.include_router(medications.router)
app.include_router(account.router)
app.include_router(household.router)
app.include_router(measurements.router)
app.include_router(vaccinations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/metrics")
async def get_metrics(user: User = Depends(get_current_user)):
    """Operational snapshot: request volume, latency, error rate, and
    OpenAI token usage. Gated behind login rather than left open - it's
    operational data, not per-user data, but there is no reason to expose
    it publicly."""
    return {"requests": metrics.summary(), "tokens": budget.stats()}
