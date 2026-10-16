"""Versioned business API. Routers of later stories are included here."""

from fastapi import APIRouter

from fenix.platform.errors import ErrorResponse

# Error bodies follow the uniform contract; declaring them here also replaces
# FastAPI's default 422 schema in OpenAPI, so the generated client types match.
api_v1 = APIRouter(
    prefix="/api/v1",
    responses={
        "4XX": {"model": ErrorResponse, "description": "Client error"},
        "5XX": {"model": ErrorResponse, "description": "Server error"},
    },
)
