import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser
from fenix.http.deps import SessionDep
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations

router = APIRouter(tags=["me"])


class Me(BaseModel):
    id: uuid.UUID
    first_name: str
    is_staff: bool = Field(description="Shows the staff section in the Mini App")


@router.get("/me")
async def me(user: CurrentUser, session: SessionDep) -> Me:
    location_id = await locations.get_default_location_id(session)
    staff = location_id is not None and await identity.is_staff(session, user.id, location_id)
    return Me(id=user.id, first_name=user.first_name, is_staff=staff)
