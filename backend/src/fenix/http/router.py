"""Versioned business API. Routers of later stories are included here."""

from fastapi import APIRouter, Depends

from fenix.http import cart, checkout, location, me, menu, orders, staff
from fenix.http.auth import current_user
from fenix.platform.errors import ErrorResponse

# Error bodies follow the uniform contract; declaring them here also replaces
# FastAPI's default 422 schema in OpenAPI, so the generated client types match.
# Every route is authenticated by default (NFR-5).
api_v1 = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(current_user)],
    responses={
        "4XX": {"model": ErrorResponse, "description": "Client error"},
        "5XX": {"model": ErrorResponse, "description": "Server error"},
    },
)
api_v1.include_router(me.router)
api_v1.include_router(location.router)
api_v1.include_router(menu.router)
api_v1.include_router(staff.router)
api_v1.include_router(cart.router)
api_v1.include_router(checkout.router)
api_v1.include_router(orders.router)
