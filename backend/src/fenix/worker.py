"""Background worker. Run with: taskiq worker fenix.worker:broker"""

from taskiq_redis import ListQueueBroker

from fenix.platform.config import get_settings

# redis-py 8 defaults to a 5 s socket timeout, which kills the worker's blocking BRPOP
# while the queue is idle; the broker's connections must wait indefinitely.
broker = ListQueueBroker(url=get_settings().redis_url, socket_timeout=None)


@broker.task
async def ping() -> str:
    return "pong"
