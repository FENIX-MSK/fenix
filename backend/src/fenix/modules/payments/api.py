"""Public API of `payments`: functions and DTOs, the only import surface for other modules."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.payments import service
from fenix.modules.payments.service import (
    OnSiteMethod,
    OrderPayment,
    OrderPaymentStatus,
    PaymentError,
    PaymentView,
)
from fenix.platform.outbox import Event, Subscription

__all__ = [
    "OnSiteMethod",
    "OrderPayment",
    "OrderPaymentStatus",
    "PaymentError",
    "PaymentView",
    "cancel_pending",
    "complete_test_payment",
    "get_payment",
    "order_payment",
    "order_payments",
    "record_on_site",
    "refund",
    "start_online",
    "subscriptions",
]


async def start_online(
    session: AsyncSession,
    order_id: uuid.UUID,
    location_id: uuid.UUID,
    amount: int,
    description: str,
) -> PaymentView:
    """A new online payment attempt (the previous unfinished one is cancelled).
    Raises PaymentError already_paid."""
    return await service.start_online(session, order_id, location_id, amount, description)


async def complete_test_payment(
    session: AsyncSession, payment_id: uuid.UUID, succeeded: bool, now: datetime
) -> PaymentView:
    """The test provider's notification, triggered by the guest's choice in the Mini App.
    Raises PaymentError payment_not_found, payment_cancelled."""
    provider_id = await service.provider_payment_id(session, payment_id)
    if provider_id is None:
        raise PaymentError("payment_not_found", 404)
    return await service.handle_notification(session, provider_id, succeeded, now)


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> PaymentView | None:
    return await service.get_payment(session, payment_id)


async def record_on_site(
    session: AsyncSession,
    order_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    method: OnSiteMethod,
    amount: int,
    user_id: uuid.UUID,
    now: datetime,
) -> PaymentView:
    """Raises PaymentError already_paid."""
    return await service.record_on_site(
        session, order_id, location_id, method=method, amount=amount, user_id=user_id, now=now
    )


async def cancel_pending(session: AsyncSession, order_id: uuid.UUID) -> None:
    await service.cancel_pending(session, order_id)


async def refund(session: AsyncSession, order_id: uuid.UUID, now: datetime) -> bool:
    return await service.refund(session, order_id, now)


async def order_payment(session: AsyncSession, order_id: uuid.UUID) -> OrderPayment:
    return (await service.order_payments(session, [order_id]))[order_id]


async def order_payments(
    session: AsyncSession, order_ids: list[uuid.UUID]
) -> dict[uuid.UUID, OrderPayment]:
    return await service.order_payments(session, order_ids)


async def _refund_cancelled(session: AsyncSession, event: Event) -> None:
    await service.refund(session, uuid.UUID(event.payload["order_id"]), datetime.now(UTC))


def subscriptions() -> list[Subscription]:
    """A cancelled order gets its online payment back, retried until the provider agrees."""
    return [Subscription("ordering.order.cancelled", "payments.refund", _refund_cancelled)]
