"""Prometheus metrics of the background processes (NFR-6). The API has its own via the
instrumentator; the worker and the bot serve theirs on a side port inside Docker."""

from prometheus_client import Gauge, start_http_server

WORKER_PORT = 9101
BOT_PORT = 9102

OUTBOX_PENDING = Gauge("fenix_outbox_pending", "Outbox events not delivered yet")
OUTBOX_OLDEST = Gauge(
    "fenix_outbox_oldest_pending_seconds", "Age of the oldest undelivered outbox event"
)
ORDERS = Gauge("fenix_orders", "Orders of the location by status (unfinished ones)", ["status"])
TELEGRAM_UP = Gauge("fenix_telegram_up", "1 when the Bot API answers through tg-egress")
WORKER_HEARTBEAT = Gauge("fenix_worker_heartbeat_timestamp", "Last worker loop, unix time")
BOT_UP = Gauge("fenix_bot_up", "1 while the bot process runs")


def serve(port: int) -> None:
    start_http_server(port)
