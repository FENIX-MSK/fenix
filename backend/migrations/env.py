import asyncio
import importlib
import importlib.util
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

import fenix.modules
from fenix.platform.config import get_settings
from fenix.platform.db import Base, create_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Every module's models, found by name: a new module's tables are picked up without
# editing this file, and no linter can drop "unused" imports here (that once made
# autogenerate emit DROP TABLE for everything).
for module in pkgutil.iter_modules(fenix.modules.__path__):
    if importlib.util.find_spec(f"fenix.modules.{module.name}.models"):
        importlib.import_module(f"fenix.modules.{module.name}.models")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
