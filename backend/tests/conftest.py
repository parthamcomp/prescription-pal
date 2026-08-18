"""Root fixtures shared by every tier.

IMPORTANT: env vars needed by app.config.Settings() (jwt_secret has no
default - see config.py) must be set before *any* `app.*` module is
imported, since `settings = Settings()` runs at import time. This file is
collected by pytest before test modules, so setting them here (not in a
fixture) is what makes `import app...` safe anywhere else in the suite.
"""
import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/app_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("STORAGE_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("STORAGE_ACCESS_KEY", "minioadmin")
os.environ.setdefault("STORAGE_SECRET_KEY", "minioadmin")
os.environ.setdefault("OPENAI_API_KEY", "test-key-unused-openai-client-is-stubbed")

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest
from freezegun import freeze_time

FROZEN_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def frozen_clock():
    """Every test that touches a clock-dependent behavior (JWT iat/exp,
    password_changed_at comparisons, invite expiry, derive_medications'
    "active" flag) must request this fixture explicitly rather than relying
    on the real system clock - see Phase 3 determinism policy."""
    with freeze_time(FROZEN_NOW) as frozen:
        yield frozen


@pytest.fixture
def fake_redis(monkeypatch):
    """In-memory Redis double for anything hitting services/rate_limit.py.
    rate_limit.py caches its client as a module-level global (`_redis`), so
    we patch that global directly rather than patching the URL - patching
    after-the-fact settings changes wouldn't affect an already-created
    client."""
    import app.services.rate_limit as rate_limit_module

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rate_limit_module, "_redis", client)
    yield client


@pytest.fixture
def stub_openai(monkeypatch):
    """Stubs the single shared OpenAI client (services/openai_client.py)
    so unit/integration tests never make a real network call. Returns the
    mock so a test can configure specific return values or assert on calls.
    Default behavior: chat completions return a minimal valid ChatResponse
    JSON string; embeddings return a fixed-length zero vector.

    embeddings.py and llm.py both do `from app.services.openai_client
    import client` - that binds their own module-level name to the same
    object openai_client.client pointed to *at import time*, so patching
    only openai_client.client leaves those two modules holding the old
    (real) client. Every module that imports the name has to be patched
    individually; missing one doesn't fail loudly, it just means that
    module quietly makes a real network call with a fake API key, which
    the app's own error-tolerant code paths (embed_text failures degrade
    to None, chat failures degrade to a fallback message) can mask as a
    passing test.
    """
    import app.services.embeddings as embeddings_module
    import app.services.llm as llm_module
    import app.services.openai_client as openai_client_module

    mock_client = AsyncMock()

    async def _default_chat(*args, **kwargs):
        resp = AsyncMock()
        resp.choices = [AsyncMock()]
        resp.choices[0].message.content = (
            '{"text": "[[general]]stub answer", "medication_name": null, "follow_ups": []}'
        )
        resp.usage = AsyncMock(prompt_tokens=10, completion_tokens=5)
        return resp

    async def _default_embed(*args, **kwargs):
        resp = AsyncMock()
        resp.data = [AsyncMock(embedding=[0.0] * 1536)]
        return resp

    mock_client.chat.completions.create = _default_chat
    mock_client.embeddings.create = _default_embed
    monkeypatch.setattr(openai_client_module, "client", mock_client)
    monkeypatch.setattr(embeddings_module, "client", mock_client)
    monkeypatch.setattr(llm_module, "client", mock_client)
    yield mock_client


@pytest.fixture
def new_uuid():
    """Deterministic-enough unique id for test data - not seeded, just a
    convenience so tests don't repeat `uuid.uuid4()` boilerplate."""
    return uuid.uuid4()
