import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_db
from app.models_db import User
from app.repositories import account_invites as invites_repo
from app.repositories import account_links as links_repo
from app.repositories import users as users_repo
from app.schemas import HouseholdStatus, InviteOut, JoinRequest, MemberOut
from app.services.rate_limit import user_rate_limit

router = APIRouter(prefix="/api/household", tags=["household"])

INVITE_TTL_DAYS = 7


@router.get("/status", response_model=HouseholdStatus)
async def household_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await links_repo.get_link_for_member(db, user.id)
    if link is not None:
        owner = await db.get(User, link.owner_user_id)
        return HouseholdStatus(owner_email=owner.email if owner else None)

    members = await links_repo.list_members(db, user.id)
    return HouseholdStatus(
        members=[MemberOut.model_validate(m) for m in members]
    )


@router.post(
    "/invite",
    response_model=InviteOut,
    dependencies=[Depends(user_rate_limit(10, 3600, "household_invite"))],
)
async def create_invite(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing_link = await links_repo.get_link_for_member(db, user.id)
    if existing_link is not None:
        raise HTTPException(
            status_code=400,
            detail="You're already sharing another account - leave it first.",
        )

    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
    invite = await invites_repo.create_invite(db, user.id, token, expires_at)
    return InviteOut(token=invite.token, expires_at=invite.expires_at)


@router.post(
    "/join",
    response_model=HouseholdStatus,
    dependencies=[Depends(user_rate_limit(10, 3600, "household_join"))],
)
async def join_household(
    body: JoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invite = await invites_repo.get_valid_by_token(db, body.token)
    if invite is None:
        raise HTTPException(status_code=400, detail="This invite link is invalid or has expired.")
    if invite.owner_user_id == user.id:
        raise HTTPException(status_code=400, detail="You can't join your own account.")

    existing_link = await links_repo.get_link_for_member(db, user.id)
    if existing_link is not None:
        raise HTTPException(
            status_code=400,
            detail="You're already sharing another account - leave it first.",
        )
    if await links_repo.has_members(db, user.id):
        raise HTTPException(
            status_code=400,
            detail="You already have your own members sharing your account.",
        )

    await links_repo.create_link(db, invite.owner_user_id, user.id)
    await invites_repo.mark_accepted(db, invite)

    owner = await db.get(User, invite.owner_user_id)
    return HouseholdStatus(owner_email=owner.email if owner else None)


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await links_repo.remove_member(db, user.id, member_id):
        raise HTTPException(status_code=404, detail="Member not found")
    return {"ok": True}


@router.post("/leave")
async def leave_household(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await links_repo.remove_self(db, user.id):
        raise HTTPException(status_code=400, detail="You're not sharing another account")
    return {"ok": True}
