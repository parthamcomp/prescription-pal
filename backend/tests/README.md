# Backend test suite

Four tiers (see the project's test-suite design doc for the full inventory
and architecture rationale). Every command below assumes you're in `backend/`
and running through the same Docker Compose stack the rest of the project
uses - there is no local Python install requirement, consistent with the
rest of this repo.

## Running

**Why `-v` is needed on every command below:** the `backend` image was last
built before `tests/`, `pyproject.toml`, and `requirements-dev.txt` existed,
so the running/pulled image doesn't have them baked in - `-v` mounts your
current source over `/app` so the container sees them. Once you rebuild the
image (`docker compose build backend`) after this suite is merged, plain
`docker compose run --rm backend ...` (no `-v`) is enough for the *code* to
be present - but `requirements-dev.txt` still needs installing each run,
since dev-only test deps are deliberately never baked into the production
image. If that install step becomes annoying, build a separate
`Dockerfile.test` (`FROM` the prod image, `RUN pip install -r
requirements-dev.txt`) and use that image for local test runs instead.

One-time setup (creates the dedicated Tier 2 test database - skip if it
already exists):
```powershell
docker compose exec -T db psql -U app -d app -c "CREATE DATABASE app_test"
```

**Schema drift gotcha:** the `engine` fixture (`tests/integration/conftest.py`)
builds `app_test`'s schema by calling `Base.metadata.create_all` against
whatever `app_test` already has - it only creates tables that don't exist
yet, it never `ALTER`s an existing one. If you change a column/constraint on
an existing table (e.g. a `ForeignKey`'s `ondelete` behavior) and `app_test`
was created before that change, `create_all` silently no-ops and the tests
run against the *old* schema - the request under test can return the right
HTTP status while the underlying DB does the wrong thing, since the schema
just didn't move. Drop and recreate `app_test` whenever this happens (safe -
it's fully rebuilt and truncated per test anyway):
```powershell
docker compose exec -T db psql -U app -d app -c "DROP DATABASE app_test" -c "CREATE DATABASE app_test"
```

```powershell
# Tier 1 - unit (target: <30s, run on every save)
docker compose run --rm -v "${PWD}\backend:/app" backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/unit -v"

# Tier 2 - integration (target: <3min, run on every commit)
# TEST_DATABASE_URL points at the dedicated test DB on the existing `db`
# service rather than spinning up testcontainers, since the backend
# container has no Docker socket mounted for Docker-in-Docker. A real CI
# runner should use testcontainers directly instead (drop
# TEST_DATABASE_URL, mount the Docker socket) - see tests/integration/conftest.py.
docker compose run --rm -v "${PWD}\backend:/app" -e TEST_DATABASE_URL="postgresql+asyncpg://app:app@db:5432/app_test" backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/integration -v"

# Tier 4 - contract (target: <1min, run on every commit)
docker compose run --rm -v "${PWD}\backend:/app" backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/contract -v"

# All backend tiers except E2E
docker compose run --rm -v "${PWD}\backend:/app" -e TEST_DATABASE_URL="postgresql+asyncpg://app:app@db:5432/app_test" backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/unit tests/integration tests/contract -v"

# Tier 3 - E2E (target: <10min, run on PR): see frontend/e2e - `npm run test:e2e`
# from frontend/, against the full docker-compose stack already running.
```

`test:changed` (backend): no dedicated tool wired up yet - for now, run
`git diff --name-only main -- 'backend/app/**/*.py'` yourself and map
changed modules to their test files by the mirrored directory structure
(`app/services/meds.py` -> `tests/unit/services/test_meds.py`). Worth
adding `pytest-testmon` if this becomes a real friction point.

## Mutation testing

```powershell
# mutmut 3.x's PytestRunner is hardcoded to bare `pytest` relying on
# pytest's own `testpaths` config - narrow testpaths to the module's test
# file first, run mutmut, then restore testpaths to ["tests"].
#   1. Edit pyproject.toml: testpaths = ["tests/unit/services/test_meds.py"]
#   2. docker compose run --rm --user root backend sh -c "pip install -q -r requirements-dev.txt && rm -rf mutants .mutmut-cache && python -m mutmut run"
#   3. python -m mutmut results   (inside the same container invocation)
#   4. Restore testpaths = ["tests"]
# --user root is needed only because the image's default non-root user
# can't create the mutants/ working directory under /app.
```

## Directory layout

Mirrors `backend/app/` under `tests/unit/` and `tests/integration/routers/` -
"where is this tested?" should never require a search.

```
tests/
  conftest.py          # frozen_clock, fake_redis, stub_openai - shared everywhere
  builders.py           # plain builder functions, not factory_boy (async session mismatch)
  unit/                 # Tier 1 - mirrors app/
    services/
      test_meds.py       # + property test (color_key_for)
      test_rate_limit.py  # + failure-injection test
  integration/           # Tier 2
    conftest.py           # real Postgres, per-test engine/session, auth_cookies()
    routers/
      test_children.py     # + authorization table + concurrency test
  contract/               # Tier 4
    test_openapi_snapshot.py
    generate_snapshot.py    # run after an intentional API change
    test_settings_smoke.py
```

## Adding a test for a new feature (5 lines)

1. Find the mirrored path: `app/routers/foo.py` -> `tests/integration/routers/test_foo.py` (or `unit/` if it's pure logic with no DB/Redis/S3).
2. Copy the closest existing test in that tier as your starting shape - `test_children.py` for a new router, `test_meds.py` for a new pure-logic module.
3. Name it `test_<behavior>_when_<condition>` - the name alone should tell someone what broke.
4. Use `tests/builders.py` for data, not hand-rolled fixtures; add a new builder there if you need a new entity.
5. If the router is protected, add the four-case authorization table (unauthenticated / wrong-account / shared-member / owner) - copy the pattern in `test_children.py`.
