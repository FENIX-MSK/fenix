"""Background worker. Run with: taskiq worker fenix.worker:broker"""

from taskiq_redis import ListQueueBroker

from fenix.config import get_settings

broker = ListQueueBroker(url=get_settings().redis_url)


@broker.task
async def ping() -> str:
    return "pong"
