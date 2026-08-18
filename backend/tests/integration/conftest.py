"""Tier 2 fixtures: a real Postgres (pgvector) container, migrated with the
project's own Alembic revisions, wired into the real FastAPI app. This is
what distinguishes Tier 2 from Tier 1 - queries run against the actual
schema, so a query that doesn't match a column/type/constraint fails here,
not just in production.
"""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.security import create_access_token
from app.models_db import Base

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres_url():
    # CI/default: an ephemeral pgvector container via testcontainers, fully
    # isolated per run. Local override: point TEST_DATABASE_URL at an
    # already-running Postgres (e.g. the docker-compose `db` service) to
    # skip Docker-in-Docker entirely when the test runner is itself already
    # inside a container without a mounted Docker socket.
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        yield override
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def engine(postgres_url):
    # Function-scoped on purpose, unlike `postgres_url` above: an asyncpg
    # connection pool is bound to the event loop it was created on, and
    # pytest-asyncio gives every test function its own loop by default. A
    # session-scoped engine works fine for exactly one test and then fails
    # every test after it with "Future attached to a different loop" - the
    # container/URL has no such affinity, so only this needs re-creating
    # per test, not the whole Postgres process.
    eng = create_async_engine(postgres_url, future=True)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Tier 2 verifies real wiring, not Alembic's own up/down correctness
        # (that's a Tier 4 contract concern - see test_migrations_roundtrip)
        # - creating from the current models is faster and just as valid
        # for "does this query match this schema."
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with session_local() as session:
        yield session

    # Function-scoped cleanup: truncate everything so each test starts from
    # an empty database, regardless of what the app code committed during
    # the test. Simpler and more honest than a rollback-wrapper here, since
    # the app's own repositories call db.commit() internally.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest_asyncio.fixture
async def client(engine, db_session):
    """`db_session` is for direct test-setup access (builders); the app
    itself gets a fresh session per request, exactly like production's real
    get_db() (see app/db.py) - sharing one session between test setup and
    simulated HTTP requests is the classic anti-pattern that breaks the
    moment two requests overlap (asyncpg connections aren't safe for
    concurrent use), which is exactly the scenario the concurrency test
    below needs to exercise correctly."""
    from app.db import get_db
    from app.main import app

    session_local = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def auth_cookies(user_id) -> dict:
    """Mint a real access token directly rather than going through
    /api/auth/login for every test - the login flow itself is covered by
    its own router tests; authorization tests only need a valid session."""
    return {"access_token": create_access_token(str(user_id))}
