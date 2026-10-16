import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from fenix.http.auth import CurrentUser

router = APIRouter(tags=["me"])


class Me(BaseModel):
    id: uuid.UUID
    first_name: str


@router.get("/me")
async def me(user: CurrentUser) -> Me:
    return Me(id=user.id, first_name=user.first_name)
