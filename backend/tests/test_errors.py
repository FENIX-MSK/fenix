import io
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fenix.http.auth import current_user
from fenix.http.openapi import build_schema
from fenix.http.router import api_v1
from fenix.main import create_app
from fenix.platform.config import Settings
from fenix.platform.errors import ApiError


class Echo(BaseModel):
    name: str
    count: int


probe = APIRouter(prefix="/probe")


@probe.post("/echo")
async def echo(body: Echo) -> Echo:
    return body


@probe.get("/boom")
async def boom() -> None:
    raise RuntimeError("secret internals")


@probe.get("/conflict")
async def conflict() -> None:
    raise ApiError(409, "order_conflict", "Order changed", {"version": 3})


@probe.get("/teapot")
async def teapot() -> None:
    raise HTTPException(418, detail={"pot": "full"})


@pytest.fixture
def app() -> Iterator[FastAPI]:
    # Mount the probe the way real routes are mounted: through api_v1, before the app is built.
    before = list(api_v1.routes)
    api_v1.include_router(probe)
    try:
        app = create_app(Settings())
        # The error contract is independent of who is calling; auth has its own tests.
        app.dependency_overrides[current_user] = lambda: None
        yield app
    finally:
        api_v1.routes[:] = before


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Unhandled errors must become a 500 response, not propagate into the test.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_unknown_v1_route_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": {}}
    }


def test_wrong_method_keeps_the_format(client: TestClient) -> None:
    response = client.get("/api/v1/probe/echo")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers["allow"] == "POST"


def test_validation_error(client: TestClient) -> None:
    response = client.post("/api/v1/probe/echo", json={"name": "борщ", "count": "много"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert [e["loc"] for e in error["details"]["errors"]] == [["body", "count"]]


def test_unhandled_exception_is_opaque(client: TestClient) -> None:
    # Same formatter as the production handler, so the assertion sees what the log sees.
    root = logging.getLogger()
    sink = io.StringIO()
    handler = logging.StreamHandler(sink)
    handler.setFormatter(root.handlers[0].formatter)
    root.addHandler(handler)
    try:
        response = client.get("/api/v1/probe/boom")
    finally:
        root.removeHandler(handler)
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": {}}
    }
    assert "secret internals" not in response.text
    logged = sink.getvalue()
    assert "http.unhandled_error" in logged
    assert "RuntimeError: secret internals" in logged


def test_api_error(client: TestClient) -> None:
    response = client.get("/api/v1/probe/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "order_conflict", "message": "Order changed", "details": {"version": 3}}
    }


def test_http_exception_dict_detail_goes_to_details(client: TestClient) -> None:
    response = client.get("/api/v1/probe/teapot")
    assert response.status_code == 418
    assert response.json() == {
        "error": {"code": "i_m_a_teapot", "message": "i_m_a_teapot", "details": {"pot": "full"}}
    }


def test_v1_errors_documented_with_uniform_schema(app: FastAPI) -> None:
    responses = app.openapi()["paths"]["/api/v1/probe/echo"]["post"]["responses"]
    assert "422" not in responses
    for status in ("4XX", "5XX"):
        schema = responses[status]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_openapi_schema_needs_no_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No token in the environment and no .env file reachable from the working directory.
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    monkeypatch.chdir(tmp_path)
    schema = build_schema()
    assert "/api/health" in schema["paths"]
    assert "/metrics" not in schema["paths"]
