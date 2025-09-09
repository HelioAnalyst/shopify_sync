import celery
from fastapi import FastAPI, Response
from app.core.logging import setup_logging
from app.core.config import settings
from app.api.routers import health, sync, shopify_webhooks, shopify_oauth, debug_webhooks
from app.api.routers import debug_bc
from app.metrics import prom
from app.api.routers import debug_orders
from app.api.routers import debug_inventory  # add
from app.api.routers import debug_celery




setup_logging(settings.LOG_LEVEL)
app = FastAPI(title="Shopify API Integration System")

# Routers
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(shopify_webhooks.router)
app.include_router(shopify_oauth.router)
app.include_router(debug_webhooks.router)
app.include_router(debug_bc.router)
app.include_router(prom.router)
app.include_router(debug_orders.router)
app.include_router(debug_inventory.router)
app.include_router(debug_celery.router)




# Metrics (optional)
if settings.PROMETHEUS_ENABLE:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    @app.get("/metrics")
    def metrics():
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
