"""Checkout data and the guest's contact (FR-7 to FR-10)."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser, LocationIdDep
from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.platform.errors import ApiError
from fenix.platform.messenger_auth import InvalidInitDataError, verify_shared_contact

router = APIRouter(tags=["checkout"])

PaymentMethod = Literal["online", "cash", "card"]


class ContactOut(BaseModel):
    first_name: str
    phone: str | None
    has_consent: bool


class CheckoutOut(BaseModel):
    is_open: bool
    status_text: str
    asap_minutes: int = Field(description="«Как можно скорее (≈N мин)»")
    fulfilment: list[Literal["pickup"]]
    payment_methods: list[PaymentMethod]
    contact: ContactOut


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
    settings = await locations.get_order_settings(session, location_id, datetime.now(UTC))
    return CheckoutOut(
        is_open=settings.status.is_open,
        status_text=settings.status.text,
        asap_minutes=settings.prep_minutes,
        fulfilment=["pickup"],
        payment_methods=["online", "cash", "card"],
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
