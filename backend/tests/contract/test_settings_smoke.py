"""Smoke coverage for config.py's fail-fast behavior (see Phase 1 inventory
"Untested-by-nature areas"). This is exactly the class of bug that crash-
looped the production worker this session: JWT_SECRET has no default, and
the failure only shows up when the process actually starts. Runs in a
subprocess with a deliberately clean environment, since the parent test
process's conftest.py has already set JWT_SECRET for every other test.
"""
import subprocess
import sys


def test_settings_raises_without_jwt_secret():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; os.environ.pop('JWT_SECRET', None); "
            "os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://a:a@localhost/a'); "
            "from app.config import Settings; Settings()",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "jwt_secret" in result.stderr.lower()


def test_settings_succeeds_with_jwt_secret():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; os.environ['JWT_SECRET'] = 'x'; "
            "os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://a:a@localhost/a'); "
            "from app.config import Settings; Settings(); print('OK')",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "OK" in result.stdout
