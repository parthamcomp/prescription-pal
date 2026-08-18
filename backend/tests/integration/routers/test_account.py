"""Tier 2 integration tests for routers/account.py - profile/password
changes and the account-deletion flow (confirm-phrase gate, blocking
deletion while shared-account members still exist, DB cascade cleanup).

delete_prefix (object storage) is mocked - Tier 2 verifies DB/API wiring,
not a real MinIO/R2 round trip, and account.py imports it directly
(`from app.services.objects import delete_prefix`), so it has to be
patched on routers.account itself, not services.objects - the same
name-binding gotcha stub_openai had (see test_stub_openai_fixture.py).
"""
from app.auth.security import verify_password
from tests.builders import make_account_link, make_child, make_prescription, make_user
from tests.integration.conftest import auth_cookies

VALID_PASSWORD = "Str0ng!Passw0rd"


class TestUpdateProfile:
    async def test_display_name_updates(self, client, db_session):
        user = await make_user(db_session)
        resp = await client.patch(
            "/api/account/profile",
            json={"display_name": "New Name"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New Name"


class TestChangePassword:
    async def test_wrong_current_password_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        resp = await client.post(
            "/api/account/change-password",
            json={"current_password": "TotallyWrong!9", "new_password": "N3w!Passw0rd"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 401

    async def test_correct_current_password_updates_it(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        resp = await client.post(
            "/api/account/change-password",
            json={"current_password": VALID_PASSWORD, "new_password": "N3w!Passw0rd"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 200

        await db_session.refresh(user)
        assert verify_password("N3w!Passw0rd", user.password_hash)
        assert not verify_password(VALID_PASSWORD, user.password_hash)

    async def test_weak_new_password_is_rejected(self, client, db_session, fake_redis):
        user = await make_user(db_session)
        resp = await client.post(
            "/api/account/change-password",
            json={"current_password": VALID_PASSWORD, "new_password": "alllowercase"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 422


class TestExportAccount:
    async def test_export_includes_children_and_prescriptions(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id, name="Riley")
        await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.get("/api/account/export", cookies=auth_cookies(owner.id))

        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        body = resp.json()
        assert body["account"]["email"] == owner.email
        assert len(body["children"]) == 1
        assert body["children"][0]["name"] == "Riley"
        assert len(body["prescriptions"]) == 1


class TestDeleteAccount:
    async def test_wrong_confirmation_phrase_is_rejected(self, client, db_session):
        user = await make_user(db_session)
        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "yes please"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 400

    async def test_correct_phrase_is_case_and_whitespace_insensitive(
        self, client, db_session, monkeypatch
    ):
        import app.routers.account as account_router

        monkeypatch.setattr(account_router, "delete_prefix", lambda prefix: None)
        user = await make_user(db_session)

        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "  Delete My Account  "},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 200

    async def test_deleting_an_account_with_active_members_is_blocked(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "delete my account"},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 400

    async def test_deletion_cascades_to_children_and_prescriptions(
        self, client, db_session, monkeypatch
    ):
        import app.routers.account as account_router
        from sqlalchemy import select

        from app.models_db import Child, Prescription, User

        monkeypatch.setattr(account_router, "delete_prefix", lambda prefix: None)
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "delete my account"},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 200

        # db_session.get() would return the identity-mapped Python object it
        # already holds from make_user() above without re-querying - a
        # fresh select() is what actually proves the row is gone from the
        # (separate) session the deletion happened through.
        assert (
            await db_session.execute(select(User).where(User.id == owner.id))
        ).scalar_one_or_none() is None
        assert (
            await db_session.execute(select(Child).where(Child.user_id == owner.id))
        ).scalar_one_or_none() is None
        assert (
            await db_session.execute(
                select(Prescription).where(Prescription.user_id == owner.id)
            )
        ).scalar_one_or_none() is None

    async def test_deletion_clears_auth_cookies(self, client, db_session, monkeypatch):
        import app.routers.account as account_router

        monkeypatch.setattr(account_router, "delete_prefix", lambda prefix: None)
        user = await make_user(db_session)

        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "delete my account"},
            cookies=auth_cookies(user.id),
        )

        set_cookie_headers = resp.headers.get_list("set-cookie")
        assert any(
            h.startswith("access_token=") and "max-age=0" in h.lower()
            for h in set_cookie_headers
        )

    async def test_object_storage_failure_does_not_block_account_deletion(
        self, client, db_session, monkeypatch
    ):
        # delete_account explicitly swallows storage-cleanup errors - the
        # account is already gone from the DB by that point, so failing the
        # whole request over an unrelated S3/R2 hiccup would leave the user
        # thinking deletion failed when it actually succeeded.
        import app.routers.account as account_router

        def _blow_up(prefix: str) -> None:
            raise ConnectionError("object storage is unreachable")

        monkeypatch.setattr(account_router, "delete_prefix", _blow_up)
        user = await make_user(db_session)

        resp = await client.request(
            "DELETE",
            "/api/account",
            json={"confirm": "delete my account"},
            cookies=auth_cookies(user.id),
        )
        assert resp.status_code == 200
