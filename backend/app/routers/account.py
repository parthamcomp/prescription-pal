import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import get_current_user, get_data_owner_id
from app.auth.security import hash_password, verify_password
from app.db import get_db
from app.models_db import User
from app.repositories import account_links as account_links_repo
from app.repositories import children as children_repo
from app.repositories import prescriptions as prescriptions_repo
from app.repositories import users as users_repo
from app.schemas import (
    DELETE_ACCOUNT_PHRASE,
    ChangePasswordRequest,
    ChildOut,
    DeleteAccountRequest,
    PrescriptionOut,
    UpdateProfileRequest,
    UserOut,
)
from app.services.objects import delete_prefix
from app.services.rate_limit import user_rate_limit

router = APIRouter(prefix="/api/account", tags=["account"])


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await users_repo.update_display_name(db, user, body.display_name.strip())


@router.post(
    "/change-password",
    dependencies=[Depends(user_rate_limit(10, 3600, "change_password"))],
)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    await users_repo.update_password(db, user, hash_password(body.new_password))
    return {"ok": True}


@router.get("/export")
async def export_account(
    user: User = Depends(get_current_user),
    owner_id: uuid.UUID = Depends(get_data_owner_id),
    db: AsyncSession = Depends(get_db),
):
    prescriptions = await prescriptions_repo.list_for_user(db, owner_id, limit=10000)
    children = await children_repo.list_for_user(db, owner_id)

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "children": [
            ChildOut.model_validate(c).model_dump(mode="json") for c in children
        ],
        "prescriptions": [
            PrescriptionOut.model_validate(p).model_dump(mode="json")
            for p in prescriptions
        ],
        "note": "This export does not include original uploaded photos - only "
        "the structured fields extracted from them.",
    }
    body = json.dumps(payload, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="prescription-pal-export.json"'
        },
    )


@router.delete("")
async def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.confirm.strip().lower() != DELETE_ACCOUNT_PHRASE:
        raise HTTPException(
            status_code=400, detail=f'Type "{DELETE_ACCOUNT_PHRASE}" to confirm.'
        )
    if await account_links_repo.has_members(db, user.id):
        raise HTTPException(
            status_code=400,
            detail="Remove everyone you've shared your account with before deleting it.",
        )
    user_id = user.id
    await users_repo.delete_user(db, user)
    try:
        # DB rows (prescriptions, children, processing_jobs) cascade-delete
        # via FK ON DELETE CASCADE, but the uploaded prescription photos
        # themselves live in object storage and nothing else removes them -
        # without this they'd outlive the account indefinitely.
        await run_in_threadpool(delete_prefix, f"uploads/{user_id}/")
    except Exception:  # noqa: BLE001 - the account is already gone; don't fail the request over storage cleanup
        pass
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"ok": True}
