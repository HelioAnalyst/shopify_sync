# app/metrics/prom.py
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()

# --- Inventory metrics -------------------------------------------------------
# Keep a single counter for "updates pushed" (no labels) so .inc() calls work.
if "shopify_inventory_updates_total" not in globals():
    shopify_inventory_updates_total = Counter(
        "shopify_inventory_updates_total",
        "Inventory updates pushed to Shopify"
    )

# Latency histogram (name matches what you're grepping for: inventory_update_seconds)
if "inventory_update_seconds" not in globals():
    inventory_update_seconds = Histogram(
        "inventory_update_seconds",
        "Latency updating inventory in Shopify (seconds)"
    )

# Optional higher-level pipeline metrics (distinct names, safe to keep)
if "INVENTORY_UPDATES_ATTEMPTED" not in globals():
    INVENTORY_UPDATES_ATTEMPTED = Counter(
        "inventory_updates_attempted_total",
        "Inventory update attempts",
        ["source"]  # e.g. "bc_to_shopify"
    )

if "INVENTORY_UPDATES_SUCCEEDED" not in globals():
    INVENTORY_UPDATES_SUCCEEDED = Counter(
        "inventory_updates_succeeded_total",
        "Successful inventory level updates",
        ["source"]
    )

if "INVENTORY_UPDATES_FAILED" not in globals():
    INVENTORY_UPDATES_FAILED = Counter(
        "inventory_updates_failed_total",
        "Failed inventory level updates",
        ["source"]
    )

if "INVENTORY_SYNC_LATENCY" not in globals():
    INVENTORY_SYNC_LATENCY = Histogram(
        "inventory_sync_seconds",
        "Latency syncing inventory"
    )

# --- Example/other metrics ---------------------------------------------------
if "WEBHOOKS_RECEIVED" not in globals():
    WEBHOOKS_RECEIVED = Counter(
        "shopify_webhooks_received_total",
        "Shopify webhooks received",
        ["topic"]
    )

if "ORDERS_PUSHED" not in globals():
    ORDERS_PUSHED = Counter(
        "bc_orders_pushed_total",
        "BC sales orders created"
    )

if "ORDERS_DEDUPED" not in globals():
    ORDERS_DEDUPED = Counter(
        "bc_orders_deduped_total",
        "BC order deduped by externalDocumentNumber"
    )

if "ORDER_PUSH_LATENCY" not in globals():
    ORDER_PUSH_LATENCY = Histogram(
        "bc_order_push_seconds",
        "Latency pushing order to BC"
    )

# Expose /metrics from this router
@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
