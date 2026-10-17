"""Checkout data and the guest's contact (FR-7 to FR-10)."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser, LocationIdDep
from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.catalog import api as catalog
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.platform.errors import ApiError
from fenix.platform.messenger_auth import InvalidInitDataError, verify_shared_contact

router = APIRouter(tags=["checkout"])

PaymentMethod = Literal["online", "cash", "card"]


class ContactOut(BaseModel):
    first_name: str
    phone: str | None
    has_consent: bool


class CheckedPromotionOut(BaseModel):
    id: uuid.UUID
    title: str
    percent: int
    # The cart total with this discount: preliminary until staff confirm it.
    preview_total: int


class CheckoutOut(BaseModel):
    is_open: bool
    status_text: str
    asap_minutes: int = Field(description="«Как можно скорее (≈N мин)»: preparation + load")
    kitchen_busy: bool
    # «Приём заказов приостановлен» (FR-30): nothing can be ordered.
    orders_paused: bool
    fulfilment: list[Literal["pickup", "delivery"]]
    # Why delivery is not offered, when it is not: "disabled" or "paused".
    delivery_unavailable: Literal["disabled", "paused"] | None
    delivery_fee: int
    # Today's preorder slots (FR-8), local time with offset.
    slots: list[datetime]
    payment_methods: list[PaymentMethod]
    contact: ContactOut
    # Discounts the guest claims here, confirmed at hand-over (FR-11, birthday).
    checked_promotions: list[CheckedPromotionOut]


class ContactIn(BaseModel):
    first_name: str | None = Field(default=None, max_length=256)
    # Telegram's signed `requestContact` response; preferred over a typed phone.
    contact_raw: str | None = Field(default=None, max_length=4096)
    phone: str | None = Field(default=None, max_length=32)
    consent: bool = False


def contact_out(contact: identity.Contact) -> ContactOut:
    return ContactOut(
        first_name=contact.first_name, phone=contact.phone, has_consent=contact.has_consent
    )


@router.get("/checkout")
async def get_checkout(
    user: CurrentUser, session: SessionDep, location_id: LocationIdDep
) -> CheckoutOut:
    now = datetime.now(UTC)
    settings = await locations.get_order_settings(session, location_id, now)
    load = await ordering.kitchen_load(session, location_id, now)
    delivery_unavailable: Literal["disabled", "paused"] | None = (
        "disabled"
        if not settings.delivery_enabled
        else ("paused" if settings.delivery_paused else None)
    )
    return CheckoutOut(
        is_open=settings.status.is_open,
        status_text=settings.status.text,
        asap_minutes=load.wait_minutes,
        kitchen_busy=load.level == "busy",
        orders_paused=settings.orders_paused,
        fulfilment=["pickup"] if delivery_unavailable else ["pickup", "delivery"],
        delivery_unavailable=delivery_unavailable,
        delivery_fee=settings.delivery_fee,
        slots=await ordering.preorder_slots(session, location_id, now),
        payment_methods=["online", "cash", "card"],
        checked_promotions=[
            CheckedPromotionOut(
                id=p.id,
                title=p.title,
                percent=p.percent,
                preview_total=(
                    await ordering.view_cart_with_claim(session, user.id, location_id, p.id)
                ).total,
            )
            for p in await catalog.active_promotions(session, location_id)
            if p.kind == "checked"
        ],
        contact=contact_out(await identity.get_contact(session, user.id)),
    )


@router.post("/me/contact")
async def update_contact(
    body: ContactIn, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> ContactOut:
    phone, verified = body.phone, False
    if body.contact_raw is not None:
        try:
            shared = verify_shared_contact(
                body.contact_raw, settings.telegram_bot_token.get_secret_value()
            )
        except InvalidInitDataError as exc:
            raise ApiError(422, "bad_contact", "The shared contact is not valid") from exc
        if shared.external_id != user.external_id:
            raise ApiError(422, "bad_contact", "The shared contact belongs to someone else")
        phone, verified = shared.phone, True
    try:
        contact = await identity.update_contact(
            session,
            user.id,
            first_name=body.first_name,
            phone=phone,
            phone_verified=verified,
            consent=body.consent,
            now=datetime.now(UTC),
        )
    except identity.ContactError as exc:
        raise ApiError(422, exc.code, "The contact was rejected") from exc
    return contact_out(contact)
