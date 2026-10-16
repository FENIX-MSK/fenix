"""Initial data of the location. Placeholders are marked for the owner to replace (story 2.7)."""

from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations.models import Location, OpeningHours

# PLACEHOLDER: the owner replaces address, coordinates and phone in the editor.
DEFAULT_LOCATION = {
    "name": "Феникс бистро",
    "timezone": "Europe/Moscow",
    "address": "Адрес уточняется",
    "latitude": None,
    "longitude": None,
    "phone": "+7 (000) 000-00-00",
    "description": "Роллы, пицца, бургеры, лепёшки, кофе и лимонады — с собой и с доставкой.",
    # From the QR codes printed on the menu.
    "social_links": [
        {"kind": "telegram", "title": "Telegram", "url": "https://t.me/phoenix_catering"},
        {
            "kind": "max",
            "title": "MAX",
            "url": "https://max.ru/u/f9LHodD0cOLIKz84G4slSSyEx8nsE00IjfVN_kgD5Au-hDoTTbLto4KeIhw",
        },
    ],
}
# PLACEHOLDER: every day 9:00-22:00 until the owner sets the real schedule.
DEFAULT_HOURS = [(weekday, time(9, 0), time(22, 0)) for weekday in range(7)]


async def seed_default_location(session: AsyncSession) -> bool:
    """Create the location once. Returns False when one exists: staff edits are kept."""
    if (await session.execute(select(Location.id).limit(1))).first() is not None:
        return False
    location = Location(**DEFAULT_LOCATION)
    location.opening_hours = [
        OpeningHours(weekday=weekday, opens_at=opens, closes_at=closes)
        for weekday, opens, closes in DEFAULT_HOURS
    ]
    session.add(location)
    await session.flush()
    return True
