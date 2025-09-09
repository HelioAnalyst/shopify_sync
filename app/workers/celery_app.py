from celery import Celery, signals
from app.core.config import settings
from app.tasks import inventory  # ensure module is imported so task is registered
from celery.schedules import crontab



celery_app = Celery(
    "shopify_sync",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    imports=(
        "app.tasks.orders",
        "app.tasks.products",
        "app.tasks.inventory",
        "app.tasks.reconciliation",
    ),
    beat_schedule={
        "reconcile-every-6h": {
            "task": "app.tasks.reconciliation.run_reconciliation",
            "schedule": 6 * 60 * 60,
        }
    },
)

celery_app.conf.beat_schedule = {
    "inventory-sync-5m": {
        "task": "app.tasks.inventory.sync_inventory_levels",
        "schedule": crontab(minute="*/5"),
        "args": [],  # full window sync
    },
}
# --- Prometheus exporter for the worker ---
import os
from prometheus_client import start_http_server

@signals.worker_ready.connect
def _start_prometheus_exporter(sender=None, **kwargs):
    """Start a single metrics HTTP server in the worker container."""
    if str(os.getenv("PROMETHEUS_ENABLE", "true")).lower() != "true":
        return
    port = int(os.getenv("PROMETHEUS_WORKER_PORT", "8001"))
    start_http_server(port)
