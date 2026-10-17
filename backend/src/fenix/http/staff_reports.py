"""Reports for the owner (FR-36). Mounted under /api/v1/staff."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel

from fenix.http.auth import LocationIdDep
from fenix.http.deps import SessionDep
from fenix.modules.locations import api as locations
from fenix.modules.reporting import api as reporting
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/reports", tags=["staff-reports"])


class DishSalesOut(BaseModel):
    title: str
    quantity: int
    revenue: int


class SalesOut(BaseModel):
    start: date
    end: date
    revenue: int
    completed: int
    orders: int
    average_check: int
    cancelled: int
    by_payment: dict[str, int]
    by_fulfilment: dict[str, int]
    top_dishes: list[DishSalesOut]
    cancel_reasons: dict[str, int]
    new_guests: dict[str, int]


def period_dates(
    period: str, today: date, start: date | None, end: date | None
) -> tuple[date, date]:
    if period == "day":
        return today, today
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return today.replace(day=1), today
    if start is None or end is None or end < start or (end - start).days > 366:
        raise ApiError(422, "bad_period", "Pick a start and an end within a year")
    return start, end


@router.get("/sales")
async def sales(
    session: SessionDep,
    location_id: LocationIdDep,
    period: Literal["day", "week", "month", "custom"] = "day",
    start: date | None = None,
    end: date | None = None,
) -> SalesOut:
    now = datetime.now(UTC)
    settings = await locations.get_order_settings(session, location_id, now)
    today = now.astimezone(ZoneInfo(settings.timezone)).date()
    first, last = period_dates(period, today, start, end)
    report = await reporting.sales_report(session, location_id, first, last, now)
    return SalesOut(
        start=report.start,
        end=report.end,
        revenue=report.revenue,
        completed=report.completed,
        orders=report.orders,
        average_check=report.average_check,
        cancelled=report.cancelled,
        by_payment=report.by_payment,
        by_fulfilment=report.by_fulfilment,
        top_dishes=[
            DishSalesOut(title=d.title, quantity=d.quantity, revenue=d.revenue)
            for d in report.top_dishes
        ],
        cancel_reasons=report.cancel_reasons,
        new_guests=report.new_guests,
    )
