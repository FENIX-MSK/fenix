"""Staff API: every route requires an active membership (AD-7)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fenix.http import staff_catalog, staff_location, staff_orders
from fenix.http.auth import CurrentStaff, LocationIdDep, current_staff
from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.identity import api as identity
from fenix.platform.errors import ApiError
from fenix.telegram.bot import bot_username

router = APIRouter(prefix="/staff", tags=["staff"], dependencies=[Depends(current_staff)])
router.include_router(staff_catalog.router)
router.include_router(staff_location.router)
router.include_router(staff_orders.router)


class StaffMe(BaseModel):
    first_name: str


class InvitationOut(BaseModel):
    url: str
    expires_at: datetime


class StaffMemberOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str | None
    username: str | None
    since: datetime
    is_me: bool


@router.get("/me")
async def staff_me(staff: CurrentStaff) -> StaffMe:
    return StaffMe(first_name=staff.first_name)


@router.post("/invitations")
async def create_invitation(
    staff: CurrentStaff, session: SessionDep, settings: SettingsDep, location_id: LocationIdDep
) -> InvitationOut:
    try:
        username = await bot_username(settings)
    except Exception as exc:
        raise ApiError(503, "telegram_unavailable", "Telegram is not reachable") from exc
    token, expires_at = await identity.create_invitation(
        session, staff.id, location_id, datetime.now(UTC)
    )
    return InvitationOut(
        url=f"https://t.me/{username}?start={identity.INVITATION_PREFIX}{token}",
        expires_at=expires_at,
    )


@router.get("/members")
async def list_members(
    staff: CurrentStaff, session: SessionDep, location_id: LocationIdDep
) -> list[StaffMemberOut]:
    return [
        StaffMemberOut(
            user_id=m.user_id,
            first_name=m.first_name,
            last_name=m.last_name,
            username=m.username,
            since=m.since,
            is_me=m.user_id == staff.id,
        )
        for m in await identity.list_staff(session, location_id)
    ]


@router.post("/members/{user_id}/disable")
async def disable_member(
    user_id: uuid.UUID, session: SessionDep, location_id: LocationIdDep
) -> None:
    try:
        await identity.disable_staff(session, location_id, user_id, datetime.now(UTC))
    except identity.StaffMemberNotFoundError as exc:
        raise ApiError(404, "staff_member_not_found", "No such active staff member") from exc
    except identity.LastStaffMemberError as exc:
        raise ApiError(
            409, "last_staff_member", "The last staff member cannot be disabled"
        ) from exc
