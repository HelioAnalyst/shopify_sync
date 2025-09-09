# app/celery_app.py
from celery import Celery

celery_app = Celery(
    "shopify_sync",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

# Option A: autodiscover
celery_app.autodiscover_tasks(["app.tasks"])

# Option B: explicit imports (bulletproof)
celery_app.conf.update(
    imports=(
        "app.tasks.inventory",        # <- this ensures set_inventory_for_sku is registered
        "app.tasks.orders",
        "app.tasks.products",
        "app.tasks.reconciliation",
    )
)
