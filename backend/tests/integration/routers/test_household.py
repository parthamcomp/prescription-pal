"""Tier 2 integration tests for routers/household.py - the shared-account
model (CLAUDE.md: "one household's data pool", full symmetric access, no
nested sharing). The invariants worth locking in here are the ones that
keep that model from becoming tangled: a member can only ever belong to one
account, an owner-with-members can't also become someone else's member,
and invite tokens are single-use and expiring.
"""
from datetime import datetime, timedelta, timezone

from tests.builders import make_account_link, make_invite, make_user
from tests.integration.conftest import auth_cookies


class TestHouseholdStatus:
    async def test_a_plain_user_with_no_sharing_gets_an_empty_status(
        self, client, db_session
    ):
        user = await make_user(db_session)
        resp = await client.get("/api/household/status", cookies=auth_cookies(user.id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["owner_email"] is None
        assert body["members"] == []

    async def test_an_owner_sees_their_members(self, client, db_session):
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.get("/api/household/status", cookies=auth_cookies(owner.id))

        assert resp.status_code == 200
        body = resp.json()
        assert body["owner_email"] is None
        assert len(body["members"]) == 1
        assert body["members"][0]["email"] == member.email

    async def test_a_member_sees_the_owners_email(self, client, db_session):
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.get("/api/household/status", cookies=auth_cookies(member.id))

        assert resp.status_code == 200
        assert resp.json()["owner_email"] == owner.email


class TestCreateInvite:
    async def test_a_plain_user_can_create_an_invite(self, client, db_session, fake_redis):
        owner = await make_user(db_session)
        resp = await client.post("/api/household/invite", cookies=auth_cookies(owner.id))

        assert resp.status_code == 200
        assert resp.json()["token"]

    async def test_a_member_of_another_account_cannot_create_their_own_invite(
        self, client, db_session, fake_redis
    ):
        # No nested sharing: a member is already "inside" someone else's
        # pool and can't also become an owner of their own shared pool.
        real_owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(
            db_session, owner_user_id=real_owner.id, member_user_id=member.id
        )

        resp = await client.post("/api/household/invite", cookies=auth_cookies(member.id))

        assert resp.status_code == 400


class TestJoinHousehold:
    async def test_a_valid_invite_creates_the_link(self, client, db_session, fake_redis):
        owner = await make_user(db_session)
        invite = await make_invite(db_session, owner.id)
        joiner = await make_user(db_session)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(joiner.id),
        )

        assert resp.status_code == 200
        assert resp.json()["owner_email"] == owner.email

        status_resp = await client.get(
            "/api/household/status", cookies=auth_cookies(joiner.id)
        )
        assert status_resp.json()["owner_email"] == owner.email

    async def test_an_unknown_token_is_rejected(self, client, db_session, fake_redis):
        joiner = await make_user(db_session)
        resp = await client.post(
            "/api/household/join",
            json={"token": "not-a-real-token"},
            cookies=auth_cookies(joiner.id),
        )
        assert resp.status_code == 400

    async def test_an_expired_invite_is_rejected(self, client, db_session, fake_redis):
        owner = await make_user(db_session)
        invite = await make_invite(
            db_session,
            owner.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        joiner = await make_user(db_session)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(joiner.id),
        )
        assert resp.status_code == 400

    async def test_an_already_accepted_invite_cannot_be_reused(
        self, client, db_session, fake_redis
    ):
        owner = await make_user(db_session)
        invite = await make_invite(
            db_session, owner.id, accepted_at=datetime.now(timezone.utc)
        )
        second_joiner = await make_user(db_session)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(second_joiner.id),
        )
        assert resp.status_code == 400

    async def test_you_cannot_join_your_own_invite(self, client, db_session, fake_redis):
        owner = await make_user(db_session)
        invite = await make_invite(db_session, owner.id)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 400

    async def test_a_user_already_sharing_another_account_cannot_join_a_second(
        self, client, db_session, fake_redis
    ):
        first_owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(
            db_session, owner_user_id=first_owner.id, member_user_id=member.id
        )
        second_owner = await make_user(db_session)
        invite = await make_invite(db_session, second_owner.id)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(member.id),
        )
        assert resp.status_code == 400

    async def test_a_user_with_their_own_members_cannot_join_someone_elses_account(
        self, client, db_session, fake_redis
    ):
        # The other half of "no nested sharing": you can't join someone
        # else's pool while people are already sharing yours.
        joiner_with_members = await make_user(db_session)
        their_member = await make_user(db_session)
        await make_account_link(
            db_session,
            owner_user_id=joiner_with_members.id,
            member_user_id=their_member.id,
        )
        other_owner = await make_user(db_session)
        invite = await make_invite(db_session, other_owner.id)

        resp = await client.post(
            "/api/household/join",
            json={"token": invite.token},
            cookies=auth_cookies(joiner_with_members.id),
        )
        assert resp.status_code == 400


class TestRemoveMember:
    async def test_the_owner_can_remove_a_member(self, client, db_session):
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.delete(
            f"/api/household/members/{member.id}", cookies=auth_cookies(owner.id)
        )
        assert resp.status_code == 200

        status_resp = await client.get(
            "/api/household/status", cookies=auth_cookies(member.id)
        )
        assert status_resp.json()["owner_email"] is None

    async def test_removing_a_member_you_do_not_own_404s(self, client, db_session):
        real_owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(
            db_session, owner_user_id=real_owner.id, member_user_id=member.id
        )
        unrelated_user = await make_user(db_session)

        resp = await client.delete(
            f"/api/household/members/{member.id}", cookies=auth_cookies(unrelated_user.id)
        )
        assert resp.status_code == 404

    async def test_removing_a_nonexistent_member_404s(self, client, db_session):
        owner = await make_user(db_session)
        resp = await client.delete(
            "/api/household/members/00000000-0000-0000-0000-000000000000",
            cookies=auth_cookies(owner.id),
        )
        assert resp.status_code == 404


class TestLeaveHousehold:
    async def test_a_member_can_leave(self, client, db_session):
        owner = await make_user(db_session)
        member = await make_user(db_session)
        await make_account_link(db_session, owner_user_id=owner.id, member_user_id=member.id)

        resp = await client.post("/api/household/leave", cookies=auth_cookies(member.id))
        assert resp.status_code == 200

        status_resp = await client.get(
            "/api/household/status", cookies=auth_cookies(member.id)
        )
        assert status_resp.json()["owner_email"] is None

    async def test_a_user_who_is_not_a_member_of_anything_cannot_leave(
        self, client, db_session
    ):
        lone_user = await make_user(db_session)
        resp = await client.post("/api/household/leave", cookies=auth_cookies(lone_user.id))
        assert resp.status_code == 400
