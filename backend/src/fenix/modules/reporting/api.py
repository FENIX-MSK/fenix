"""Public API of `reporting`: functions and DTOs, the only import surface for other modules."""

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.reporting import sales
from fenix.modules.reporting.sales import DishSales, SalesReport

__all__ = ["DishSales", "SalesReport", "sales_report"]


async def sales_report(
    session: AsyncSession, location_id: uuid.UUID, start: date, end: date, now: datetime
) -> SalesReport:
    """Revenue (handed over and delivered), counts, average check, breakdowns, top dishes,
    cancellations by reason and new guests by source for local dates start..end."""
    return await sales.sales_report(session, location_id, start, end, now)
