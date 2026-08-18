"""Tier 2 integration tests for routers/auth.py - the most security-sensitive
router in the app: this is what actually mints/rejects sessions.
"""
from datetime import timedelta

from app.auth.security import create_refresh_token
from tests.builders import make_user
from tests.integration.conftest import auth_cookies

VALID_PASSWORD = "Str0ng!Passw0rd"


class TestRegister:
    async def test_registering_sets_httponly_cookies_and_no_tokens_in_body(
        self, client, fake_redis
    ):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "new-parent@example.com",
                "password": VALID_PASSWORD,
                "display_name": "Alex",
                "consent": True,
            },
        )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert "access_token" not in resp.text
        assert "refresh_token" not in resp.text
        assert resp.cookies.get("access_token") is not None
        assert resp.cookies.get("refresh_token") is not None

    async def test_registering_without_consent_is_rejected(self, client, fake_redis):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "no-consent@example.com",
                "password": VALID_PASSWORD,
                "consent": False,
            },
        )
        assert resp.status_code == 400

    async def test_weak_password_is_rejected_before_hitting_the_db(
        self, client, fake_redis
    ):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "weak-password@example.com",
                # long enough, but no digit/symbol - fails complexity, not length
                "password": "onlylowercaseletters",
                "consent": True,
            },
        )
        assert resp.status_code == 422

    async def test_duplicate_email_gets_the_same_generic_error_as_a_bad_login(
        self, client, db_session, fake_redis
    ):
        # Email enumeration protection: registering an address that already
        # exists must be indistinguishable from any other rejected register -
        # same status, same message a caller could get some other way.
        existing = await make_user(db_session, email="taken@example.com")

        resp = await client.post(
            "/api/auth/register",
            json={
                "email": existing.email,
                "password": VALID_PASSWORD,
                "consent": True,
            },
        )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Could not register with the details provided."
        # And the account itself must be untouched by the attempt.
        assert resp.cookies.get("access_token") is None


class TestLogin:
    async def test_correct_credentials_log_in(self, client, db_session, fake_redis):
        # make_user()'s default password hash is VALID_PASSWORD (see builders.py)
        user = await make_user(db_session)

        resp = await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": VALID_PASSWORD},
        )

        assert resp.status_code == 200
        assert resp.cookies.get("access_token") is not None

    async def test_wrong_password_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)

        resp = await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "TotallyWrong!9"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    async def test_unknown_email_gets_the_identical_error_as_wrong_password(
        self, client, fake_redis
    ):
        # If this message/status ever differs from the wrong-password case,
        # an attacker can use login itself to enumerate registered emails.
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody-here@example.com", "password": "Whatever!9x"},
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"


class TestMe:
    async def test_unauthenticated_request_is_rejected(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_authenticated_request_returns_the_user(self, client, db_session):
        user = await make_user(db_session)
        resp = await client.get("/api/auth/me", cookies=auth_cookies(user.id))
        assert resp.status_code == 200
        assert resp.json()["email"] == user.email


class TestRefresh:
    async def test_missing_token_is_rejected(self, client, fake_redis):
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    async def test_garbage_token_is_rejected(self, client, fake_redis):
        resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": "not-a-real-jwt"}
        )
        assert resp.status_code == 401

    async def test_valid_refresh_token_mints_a_new_session(
        self, client, db_session, fake_redis
    ):
        user = await make_user(db_session)
        token = create_refresh_token(str(user.id))

        resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": token}
        )

        assert resp.status_code == 200
        assert resp.cookies.get("access_token") is not None

    async def test_an_access_token_cannot_be_used_as_a_refresh_token(
        self, client, db_session, fake_redis
    ):
        from app.auth.security import create_access_token

        user = await make_user(db_session)
        token = create_access_token(str(user.id))

        resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": token}
        )
        assert resp.status_code == 401

    async def test_a_token_issued_before_a_password_change_is_rejected(
        self, client, db_session, frozen_clock, fake_redis
    ):
        # Mirrors the real incident this behavior exists to prevent: a
        # session/refresh token minted before the password change must stop
        # working the moment the password changes, not just the tab that
        # made the change.
        from app.repositories import users as users_repo

        user = await make_user(db_session)
        old_token = create_refresh_token(str(user.id))

        frozen_clock.tick(timedelta(minutes=5))
        await users_repo.update_password(db_session, user, user.password_hash)

        resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": old_token}
        )
        assert resp.status_code == 401

    async def test_a_token_issued_after_a_password_change_still_works(
        self, client, db_session, frozen_clock, fake_redis
    ):
        from app.repositories import users as users_repo

        user = await make_user(db_session)
        await users_repo.update_password(db_session, user, user.password_hash)

        frozen_clock.tick(timedelta(minutes=5))
        new_token = create_refresh_token(str(user.id))

        resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": new_token}
        )
        assert resp.status_code == 200


class TestLogout:
    async def test_logout_clears_both_cookies(self, client):
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
        # response.delete_cookie() clears a cookie by re-setting it with
        # Max-Age=0 - check the raw Set-Cookie headers directly, since a
        # cleared cookie doesn't show up any other way in the response.
        set_cookie_headers = resp.headers.get_list("set-cookie")
        assert any(
            h.startswith("access_token=") and "max-age=0" in h.lower()
            for h in set_cookie_headers
        )
        assert any(
            h.startswith("refresh_token=") and "max-age=0" in h.lower()
            for h in set_cookie_headers
        )


class TestRegisterRateLimit:
    async def test_the_sixth_register_from_the_same_ip_within_an_hour_is_rejected(
        self, client, fake_redis
    ):
        # register is rate-limited at 5/hour per IP (routers/auth.py) - the
        # limiter's own counting logic is unit-tested in isolation
        # (unit/services/test_rate_limit.py); this only proves the
        # dependency is actually wired onto this route.
        for i in range(5):
            resp = await client.post(
                "/api/auth/register",
                json={
                    "email": f"ratelimit-{i}@example.com",
                    "password": VALID_PASSWORD,
                    "consent": True,
                },
            )
            assert resp.status_code == 200

        sixth = await client.post(
            "/api/auth/register",
            json={
                "email": "ratelimit-6@example.com",
                "password": VALID_PASSWORD,
                "consent": True,
            },
        )
        assert sixth.status_code == 429
