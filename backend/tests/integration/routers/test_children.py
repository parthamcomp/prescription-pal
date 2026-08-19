"""Tier 2 integration tests for routers/children.py against a real Postgres
container.

Contains the AUTHORIZATION-TABLE and CONCURRENCY reference implementations.
"""
import asyncio

from sqlalchemy import select

from app.models_db import Prescription
from tests.builders import make_account_link, make_child, make_prescription, make_user
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


# --------------------------------------------------------------------------
# DELETE-CASCADE REFERENCE IMPLEMENTATION
# A child now owns their prescriptions (see models_db.py:Prescription.child_id
# and CLAUDE.md's "no unassigned records" policy) - removing the child must
# remove their records with it via the DB's ON DELETE CASCADE, not silently
# null the FK. This is exactly the kind of thing that looks right by
# inspection (the ORM column declares ondelete="CASCADE") and is wrong at
# runtime unless the relationship() also has passive_deletes=True - without
# it, SQLAlchemy's own unit-of-work nulls the FK before the DELETE ever
# reaches Postgres, so the CASCADE constraint never actually fires. Caught
# live via manual browser verification before this test existed; this test
# is what stops it silently regressing.
# --------------------------------------------------------------------------
class TestDeleteChildCascadesPrescriptions:
    async def test_deleting_a_child_deletes_their_prescriptions(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.delete(
            f"/api/children/{child.id}", cookies=auth_cookies(owner.id)
        )
        assert resp.status_code == 200

        remaining = await db_session.execute(
            select(Prescription).where(Prescription.id == prescription.id)
        )
        assert remaining.scalar_one_or_none() is None

    async def test_deleting_a_child_leaves_another_childs_prescriptions_alone(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        keep_child = await make_child(db_session, owner.id)
        delete_child = await make_child(db_session, owner.id)
        kept = await make_prescription(db_session, owner.id, child_id=keep_child.id)
        await make_prescription(db_session, owner.id, child_id=delete_child.id)

        resp = await client.delete(
            f"/api/children/{delete_child.id}", cookies=auth_cookies(owner.id)
        )
        assert resp.status_code == 200

        remaining = await db_session.execute(select(Prescription))
        remaining_ids = {row.id for row in remaining.scalars().all()}
        assert remaining_ids == {kept.id}


# --------------------------------------------------------------------------
# CRUD coverage: create/list/update/delete, filling in what the
# authorization-table and concurrency reference tests above (both scoped to
# GET) don't exercise.
# --------------------------------------------------------------------------
class TestCreateChild:
    async def test_creates_and_returns_the_child(self, client, db_session):
        owner = await make_user(db_session)
        resp = await client.post(
            "/api/children",
            json={"name": "Riley", "date_of_birth": "2022-03-01"},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Riley"
        assert body["date_of_birth"] == "2022-03-01"

    async def test_duplicate_name_on_the_same_account_is_rejected(self, client, db_session):
        owner = await make_user(db_session)
        await make_child(db_session, owner.id, name="Riley")

        resp = await client.post(
            "/api/children",
            json={"name": "Riley", "date_of_birth": None},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 400

    async def test_the_same_name_is_fine_on_a_different_account(self, client, db_session):
        owner_a = await make_user(db_session)
        owner_b = await make_user(db_session)
        await make_child(db_session, owner_a.id, name="Riley")

        resp = await client.post(
            "/api/children",
            json={"name": "Riley", "date_of_birth": None},
            cookies=auth_cookies(owner_b.id),
        )
        assert resp.status_code == 200


class TestListChildren:
    async def test_only_lists_the_callers_own_children(self, client, db_session):
        owner = await make_user(db_session)
        stranger = await make_user(db_session)
        await make_child(db_session, owner.id, name="Mine")
        await make_child(db_session, stranger.id, name="NotMine")

        resp = await client.get("/api/children", cookies=auth_cookies(owner.id))

        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert names == ["Mine"]


class TestUpdateChild:
    async def test_updates_name_and_date_of_birth(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id, name="Old Name")

        resp = await client.patch(
            f"/api/children/{child.id}",
            json={"name": "New Name", "date_of_birth": "2023-01-01"},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["date_of_birth"] == "2023-01-01"

    async def test_renaming_to_a_name_already_used_on_the_account_is_rejected(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        await make_child(db_session, owner.id, name="Taken")
        other = await make_child(db_session, owner.id, name="Renaming Me")

        resp = await client.patch(
            f"/api/children/{other.id}",
            json={"name": "Taken", "date_of_birth": None},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 400

    async def test_updating_someone_elses_child_404s(self, client, db_session):
        owner = await make_user(db_session)
        stranger = await make_user(db_session)
        child = await make_child(db_session, owner.id)

        resp = await client.patch(
            f"/api/children/{child.id}",
            json={"name": "Hijacked", "date_of_birth": None},
            cookies=auth_cookies(stranger.id),
        )
        assert resp.status_code == 404

    async def test_updating_a_nonexistent_child_404s(self, client, db_session):
        owner = await make_user(db_session)
        resp = await client.patch(
            "/api/children/00000000-0000-0000-0000-000000000000",
            json={"name": "Whoever", "date_of_birth": None},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 404


class TestDeleteChildAuthorization:
    async def test_deleting_someone_elses_child_404s(self, client, db_session):
        owner = await make_user(db_session)
        stranger = await make_user(db_session)
        child = await make_child(db_session, owner.id)

        resp = await client.delete(
            f"/api/children/{child.id}", cookies=auth_cookies(stranger.id)
        )
        assert resp.status_code == 404

    async def test_deleting_a_nonexistent_child_404s(self, client, db_session):
        owner = await make_user(db_session)
        resp = await client.delete(
            "/api/children/00000000-0000-0000-0000-000000000000",
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 404
