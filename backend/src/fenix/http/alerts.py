"""Grafana's alert webhook (NFR-6). Internal: Caddy does not route /api/internal/*."""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Header

from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.notifications import api as notifications
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/api/internal", include_in_schema=False)


@router.post("/alerts")
async def receive_alerts(
    body: dict[str, Any],
    session: SessionDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    token = settings.alerts_webhook_token
    expected = f"Bearer {token.get_secret_value()}" if token else None
    if expected is None or not hmac.compare_digest(authorization or "", expected):
        raise ApiError(401, "unauthorized", "Bad alert token")
    items = [
        {
            "status": str(alert.get("status", "firing")),
            "name": str(alert.get("labels", {}).get("alertname", "alert")),
            "summary": str(alert.get("annotations", {}).get("summary", "")),
        }
        for alert in body.get("alerts", [])
        if isinstance(alert, dict)
    ][:20]
    notifications.queue_alerts(session, items)
    return {"queued": len(items)}
