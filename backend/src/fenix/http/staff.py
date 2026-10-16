"""Staff API: every route requires an active membership (AD-7)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fenix.http.auth import CurrentStaff, LocationIdDep, current_staff
from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.identity import api as identity
from fenix.platform.errors import ApiError
from fenix.telegram.bot import bot_username

router = APIRouter(prefix="/staff", tags=["staff"], dependencies=[Depends(current_staff)])


class StaffMe(BaseModel):
    first_name: str


class InvitationOut(BaseModel):
    url: str
    expires_at: datetime


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
