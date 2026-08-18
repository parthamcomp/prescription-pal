"""Tier 2 integration tests for routers/children.py against a real Postgres
container.

Contains the AUTHORIZATION-TABLE and CONCURRENCY reference implementations.
"""
import asyncio

from tests.builders import make_account_link, make_child, make_user
from tests.integration.conftest import auth_cookies


# --------------------------------------------------------------------------
# AUTHORIZATION TABLE REFERENCE IMPLEMENTATION
# Pattern: four mechanical cases per protected resource - unauthenticated,
# authenticated-but-wrong-account, authenticated-via-shared-access,
# authenticated-as-owner. This app has no role system, so "wrong role"
# becomes "not linked to this account's data pool" - the axis that actually
# exists here (see get_data_owner_id, CLAUDE.md "Shared accounts").
# --------------------------------------------------------------------------
class TestGetChildAuthorization:
    async def test_unauthenticated_request_is_rejected(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)

        resp = await client.get(f"/api/children/{child.id}")

        assert resp.status_code == 401

    async def test_a_different_unrelated_account_cannot_see_the_child(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        stranger = await make_user(db_session)

        resp = await client.get(
            f"/api/children/{child.id}", cookies=auth_cookies(stranger.id)
        )

        # 404, not 403 - matches the app's existing pattern of not
        # confirming a resource exists to an account with no claim to it.
        assert resp.status_code == 404

    async def test_a_shared_account_member_can_see_the_child(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.get(
            f"/api/children/{child.id}", cookies=auth_cookies(member.id)
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(child.id)

    async def test_the_owner_can_see_their_own_child(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)

        resp = await client.get(
            f"/api/children/{child.id}", cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(child.id)


# --------------------------------------------------------------------------
# CONCURRENCY REFERENCE IMPLEMENTATION
# Pattern: fire the read-modify-write concurrently and assert the invariant
# holds (here: the DB-level uq_children_user_name constraint - "a user
# never has two children with the same name" - must survive a real race,
# not just sequential requests).
# --------------------------------------------------------------------------
class TestConcurrentChildCreation:
    async def test_only_one_of_two_concurrent_same_name_creates_succeeds(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        cookies = auth_cookies(owner.id)

        async def create():
            return await client.post(
                "/api/children",
                json={"name": "Riley", "date_of_birth": None},
                cookies=cookies,
            )

        first, second = await asyncio.gather(create(), create())
        statuses = sorted([first.status_code, second.status_code])

        # Exactly one 200 and one clean 400 (IntegrityError caught by the
        # router) - never two 200s (duplicate row) and never a 500.
        assert statuses == [200, 400]
