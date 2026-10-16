"""Server-side staff commands, the fallback for the first staff member.

Usage: fenix-staff bootstrap --telegram-id <id>
"""

import argparse
import asyncio
import sys

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.platform.config import get_settings
from fenix.platform.db import create_engine, create_session_factory


async def bootstrap(telegram_id: int) -> str | None:
    """None on success, otherwise the reason it was refused."""
    engine = create_engine(get_settings().database_url)
    try:
        async with create_session_factory(engine)() as session, session.begin():
            user = await identity.find_user(session, identity.Platform.TELEGRAM, str(telegram_id))
            if user is None:
                return "unknown user: they must press «Старт» in the bot first"
            location_id = await locations.get_default_location_id(session)
            if location_id is None:
                return "no location: run fenix-seed first"
            if not await identity.bootstrap_first_staff(session, user.id, location_id):
                return "the location already has staff: use an invitation"
            return None
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="fenix-staff")
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("bootstrap", help="make the first staff member")
    first.add_argument("--telegram-id", type=int, required=True)
    args = parser.parse_args()
    error = asyncio.run(bootstrap(args.telegram_id))
    if error:
        sys.exit(error)
    print("ok: staff member added")


if __name__ == "__main__":
    main()
