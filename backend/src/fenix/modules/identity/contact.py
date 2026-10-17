"""The guest's contact and privacy consent (FR-9, FR-10)."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity.models import IdentityUser


class ContactError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Contact:
    first_name: str
    phone: str | None
    phone_verified: bool
    has_consent: bool


def normalize_phone(raw: str) -> str:
    """Russian numbers to +7XXXXXXXXXX; other countries kept as +digits."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    if 10 <= len(digits) <= 15 and raw.strip().startswith("+"):
        return "+" + digits
    raise ContactError("bad_phone")


async def _user(session: AsyncSession, user_id: uuid.UUID) -> IdentityUser:
    user = await session.get(IdentityUser, user_id)
    if user is None:
        raise ContactError("user_not_found")
    return user


async def get(session: AsyncSession, user_id: uuid.UUID) -> Contact:
    user = await _user(session, user_id)
    return Contact(
        first_name=user.first_name,
        phone=user.phone,
        phone_verified=user.phone_verified,
        has_consent=user.privacy_consent_at is not None,
    )


async def update(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    first_name: str | None,
    phone: str | None,
    phone_verified: bool,
    consent: bool,
    now: datetime,
) -> Contact:
    user = await _user(session, user_id)
    if first_name is not None:
        if not first_name.strip():
            raise ContactError("name_required")
        user.first_name = first_name.strip()[:256]
    if phone is not None:
        user.phone = normalize_phone(phone)
        user.phone_verified = phone_verified
    # Consent is only ever given here, never withdrawn by this call.
    if consent and user.privacy_consent_at is None:
        user.privacy_consent_at = now
    await session.flush()
    return await get(session, user_id)
