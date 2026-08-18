"""Tier 2 integration tests for routers/prescriptions.py, focused on the
child-assignment rules added this session: every prescription now requires
a child_id, and the router checks that id actually belongs to the caller's
account rather than trusting a bare UUID (see _require_owned_child).
"""
from tests.builders import (
    make_account_link,
    make_child,
    make_prescription,
    make_user,
    prescription_payload,
)
from tests.integration.conftest import auth_cookies


class TestGetPrescriptionAuthorization:
    async def test_unauthenticated_request_is_rejected(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.get(f"/api/prescriptions/{prescription.id}")

        assert resp.status_code == 401

    async def test_a_different_unrelated_account_cannot_see_the_prescription(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)
        stranger = await make_user(db_session)

        resp = await client.get(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(stranger.id)
        )

        assert resp.status_code == 404

    async def test_a_shared_account_member_can_see_the_prescription(
        self, client, db_session
    ):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.get(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(member.id)
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(prescription.id)

    async def test_the_owner_can_see_their_own_prescription(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.get(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(prescription.id)


class TestCreatePrescriptionRequiresAnOwnedChild:
    async def test_missing_child_id_is_rejected(self, client, db_session, stub_openai):
        owner = await make_user(db_session)
        payload = prescription_payload()  # deliberately no child_id

        resp = await client.post(
            "/api/prescriptions", json=payload, cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 422

    async def test_a_child_id_belonging_to_another_account_is_rejected(
        self, client, db_session, stub_openai
    ):
        owner = await make_user(db_session)
        stranger = await make_user(db_session)
        someone_elses_child = await make_child(db_session, stranger.id)
        payload = prescription_payload(child_id=str(someone_elses_child.id))

        resp = await client.post(
            "/api/prescriptions", json=payload, cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 400

    async def test_a_nonexistent_child_id_is_rejected(self, client, db_session, stub_openai):
        owner = await make_user(db_session)
        payload = prescription_payload(child_id="00000000-0000-0000-0000-000000000000")

        resp = await client.post(
            "/api/prescriptions", json=payload, cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 400

    async def test_a_shared_members_own_child_is_accepted(
        self, client, db_session, stub_openai
    ):
        # The child only needs to belong to the resolved data-owner account,
        # not literally to the authenticated user - a shared-account member
        # creating a record for the owner's child is the normal case.
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)
        child = await make_child(db_session, owner.id)
        payload = prescription_payload(child_id=str(child.id))

        resp = await client.post(
            "/api/prescriptions", json=payload, cookies=auth_cookies(member.id)
        )

        assert resp.status_code == 200
        assert resp.json()["child_id"] == str(child.id)

    async def test_owned_child_id_succeeds_and_round_trips(
        self, client, db_session, stub_openai
    ):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        payload = prescription_payload(child_id=str(child.id))

        resp = await client.post(
            "/api/prescriptions", json=payload, cookies=auth_cookies(owner.id)
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["child_id"] == str(child.id)
        assert body["medications"][0]["name"] == "Amoxicillin"


class TestUpdatePrescriptionRequiresAnOwnedChild:
    async def test_reassigning_to_an_unowned_child_is_rejected(
        self, client, db_session, stub_openai
    ):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)
        stranger = await make_user(db_session)
        someone_elses_child = await make_child(db_session, stranger.id)

        payload = prescription_payload(child_id=str(someone_elses_child.id))
        resp = await client.put(
            f"/api/prescriptions/{prescription.id}",
            json=payload,
            cookies=auth_cookies(owner.id),
        )

        assert resp.status_code == 400

    async def test_editing_fields_persists(self, client, db_session, stub_openai):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)

        payload = prescription_payload(child_id=str(child.id), doctor_name="Dr. New")
        resp = await client.put(
            f"/api/prescriptions/{prescription.id}",
            json=payload,
            cookies=auth_cookies(owner.id),
        )

        assert resp.status_code == 200
        assert resp.json()["doctor_name"] == "Dr. New"

    async def test_updating_someone_elses_prescription_404s(
        self, client, db_session, stub_openai
    ):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)
        stranger = await make_user(db_session)
        stranger_child = await make_child(db_session, stranger.id)

        payload = prescription_payload(child_id=str(stranger_child.id))
        resp = await client.put(
            f"/api/prescriptions/{prescription.id}",
            json=payload,
            cookies=auth_cookies(stranger.id),
        )

        assert resp.status_code == 404


class TestDeletePrescription:
    async def test_deleting_someone_elses_prescription_404s(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)
        stranger = await make_user(db_session)

        resp = await client.delete(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(stranger.id)
        )

        assert resp.status_code == 404

    async def test_owner_can_delete_their_own_prescription(self, client, db_session):
        owner = await make_user(db_session)
        child = await make_child(db_session, owner.id)
        prescription = await make_prescription(db_session, owner.id, child_id=child.id)

        resp = await client.delete(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(owner.id)
        )
        assert resp.status_code == 200

        follow_up = await client.get(
            f"/api/prescriptions/{prescription.id}", cookies=auth_cookies(owner.id)
        )
        assert follow_up.status_code == 404


class TestListPrescriptionsFiltersByChild:
    async def test_child_id_query_param_narrows_the_list(self, client, db_session):
        owner = await make_user(db_session)
        child_a = await make_child(db_session, owner.id)
        child_b = await make_child(db_session, owner.id)
        await make_prescription(db_session, owner.id, child_id=child_a.id)
        await make_prescription(db_session, owner.id, child_id=child_b.id)

        resp = await client.get(
            "/api/prescriptions",
            params={"child_id": str(child_a.id)},
            cookies=auth_cookies(owner.id),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["child_id"] == str(child_a.id)
