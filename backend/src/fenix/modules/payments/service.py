import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.payments.models import Payment
from fenix.modules.payments.provider import MockProvider, PaymentProvider
from fenix.platform import outbox

OrderPaymentStatus = Literal["unpaid", "pending", "failed", "paid", "refunded"]
OnSiteMethod = Literal["cash", "card"]

provider: PaymentProvider = MockProvider()


class PaymentError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True, slots=True)
class PaymentView:
    id: uuid.UUID
    order_id: uuid.UUID
    attempt: int
    method: str
    status: str
    amount: int
    confirmation_url: str | None
    paid_at: datetime | None


@dataclass(frozen=True, slots=True)
class OrderPayment:
    status: OrderPaymentStatus
    method: str | None
    paid_at: datetime | None
    # The attempt the guest may still complete.
    pending_payment_id: uuid.UUID | None


def _view(row: Payment, confirmation_url: str | None = None) -> PaymentView:
    return PaymentView(
        row.id,
        row.order_id,
        row.attempt,
        row.method,
        row.status,
        row.amount,
        confirmation_url,
        row.paid_at,
    )


async def _attempts(session: AsyncSession, order_id: uuid.UUID) -> list[Payment]:
    statement = select(Payment).where(Payment.order_id == order_id).order_by(Payment.attempt)
    return list((await session.execute(statement)).scalars())


def _event(name: str, row: Payment, **extra: object) -> dict[str, object]:
    return {
        "payment_id": str(row.id),
        "order_id": str(row.order_id),
        "location_id": str(row.location_id),
        "method": row.method,
        "amount": row.amount,
        "status": row.status,
        **extra,
    }


async def _next_attempt(session: AsyncSession, order_id: uuid.UUID) -> int:
    # Serialise attempts of one order: two taps on «Повторить» do not race.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"payments:{order_id}"))))
    current = await session.execute(
        select(func.coalesce(func.max(Payment.attempt), 0)).where(Payment.order_id == order_id)
    )
    return current.scalar_one() + 1


async def start_online(
    session: AsyncSession,
    order_id: uuid.UUID,
    location_id: uuid.UUID,
    amount: int,
    description: str,
) -> PaymentView:
    """A new online attempt; earlier unfinished attempts are cancelled."""
    attempt = await _next_attempt(session, order_id)
    for row in await _attempts(session, order_id):
        if row.status == "paid":
            raise PaymentError("already_paid", 409)
        if row.status == "pending":
            row.status = "cancelled"
    row = Payment(
        order_id=order_id,
        location_id=location_id,
        attempt=attempt,
        method="online",
        status="pending",
        amount=amount,
        provider=provider.name,
    )
    session.add(row)
    await session.flush()
    created = await provider.create(row.id, amount, description)
    row.provider_payment_id = created.provider_payment_id
    await session.flush()
    return _view(row, created.confirmation_url)


async def handle_notification(
    session: AsyncSession, provider_payment_id: str, succeeded: bool, now: datetime
) -> PaymentView:
    """The provider's word on a payment. Repeats are no-ops (AD-9)."""
    row = (
        await session.execute(
            select(Payment)
            .where(Payment.provider_payment_id == provider_payment_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise PaymentError("payment_not_found", 404)
    if row.status in ("paid", "failed", "refunded"):
        return _view(row)
    if row.status == "cancelled":
        # The order was cancelled or a newer attempt started: this one cannot be paid.
        raise PaymentError("payment_cancelled", 409)
    if succeeded:
        row.status = "paid"
        row.paid_at = now
        outbox.emit(session, "payments.payment.succeeded", _event("succeeded", row))
    else:
        row.status = "failed"
        outbox.emit(session, "payments.payment.failed", _event("failed", row))
    await session.flush()
    return _view(row)


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> PaymentView | None:
    row = await session.get(Payment, payment_id)
    return _view(row) if row else None


async def provider_payment_id(session: AsyncSession, payment_id: uuid.UUID) -> str | None:
    row = await session.get(Payment, payment_id)
    return row.provider_payment_id if row else None


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
    """Staff took the money at the counter (FR-14): method, who and when are kept."""
    attempt = await _next_attempt(session, order_id)
    for existing in await _attempts(session, order_id):
        if existing.status == "paid":
            raise PaymentError("already_paid", 409)
        if existing.status == "pending":
            existing.status = "cancelled"
    row = Payment(
        order_id=order_id,
        location_id=location_id,
        attempt=attempt,
        method=method,
        status="paid",
        amount=amount,
        recorded_by=user_id,
        paid_at=now,
    )
    session.add(row)
    await session.flush()
    outbox.emit(session, "payments.payment.recorded", _event("recorded", row))
    return _view(row)


async def cancel_pending(session: AsyncSession, order_id: uuid.UUID) -> None:
    for row in await _attempts(session, order_id):
        if row.status == "pending":
            row.status = "cancelled"
    await session.flush()


async def refund(session: AsyncSession, order_id: uuid.UUID, now: datetime) -> bool:
    """Return an online payment (FR-15); True when there was one to return."""
    for row in await _attempts(session, order_id):
        if row.status == "paid" and row.method == "online" and row.provider_payment_id:
            await provider.refund(row.provider_payment_id, row.amount)
            row.status = "refunded"
            row.refunded_at = now
            outbox.emit(session, "payments.payment.refunded", _event("refunded", row))
            await session.flush()
            return True
        if row.status == "pending":
            row.status = "cancelled"
    await session.flush()
    return False


def _project(rows: list[Payment]) -> OrderPayment:
    status: OrderPaymentStatus = "unpaid"
    method: str | None = None
    paid_at: datetime | None = None
    pending: uuid.UUID | None = None
    for row in rows:  # by attempt: the latest meaningful state wins
        if row.status == "paid":
            status, method, paid_at = "paid", row.method, row.paid_at
        elif row.status == "refunded":
            status, method, paid_at = "refunded", row.method, row.paid_at
        elif row.status == "pending" and status not in ("paid", "refunded"):
            status, pending = "pending", row.id
        elif row.status == "failed" and status not in ("paid", "refunded"):
            status, pending = "failed", None
    return OrderPayment(status, method, paid_at, pending)


async def order_payments(
    session: AsyncSession, order_ids: list[uuid.UUID]
) -> dict[uuid.UUID, OrderPayment]:
    if not order_ids:
        return {}
    statement = select(Payment).where(Payment.order_id.in_(order_ids)).order_by(Payment.attempt)
    grouped: dict[uuid.UUID, list[Payment]] = {order_id: [] for order_id in order_ids}
    for row in (await session.execute(statement)).scalars():
        grouped[row.order_id].append(row)
    return {order_id: _project(rows) for order_id, rows in grouped.items()}
