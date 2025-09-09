# app/tasks/inventory.py
from __future__ import annotations

from typing import Dict, Any, List, Optional
import json
import requests
import structlog
from celery import shared_task

from app.bc365.client import BC365Client
from app.shopify.client import ShopifyClient
from app.core.config import settings
from app.metrics.prom import (
    INVENTORY_UPDATES_ATTEMPTED,
    INVENTORY_UPDATES_SUCCEEDED,
    INVENTORY_UPDATES_FAILED,
    INVENTORY_SYNC_LATENCY,
    inventory_update_seconds,
    shopify_inventory_updates_total,
)
from app.utils.retry import RetryableHTTPError

log = structlog.get_logger(__name__)


def _reverse_sku_map() -> Dict[str, str]:
    """
    Return BC ItemNo -> Shopify SKU mapping by reversing SKU_MAP_JSON if present.
    (Original map is ShopifySKU -> BC ItemNo)
    """
    if not settings.SKU_MAP_JSON:
        return {}
    try:
        m = json.loads(settings.SKU_MAP_JSON)
        return {v: k for k, v in m.items()}
    except Exception:
        return {}


def _bc_iter_items(bc: BC365Client, only_numbers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Fetch items from BC (number + inventory). Optionally filter by ItemNo list.
    """
    items = bc.list_items_select(fields=["number", "inventory"])  # implement in BC client if not present
    if only_numbers:
        only = set(only_numbers)
        return [i for i in items if i.get("number") in only]
    return items


@shared_task(
    bind=True,
    autoretry_for=(requests.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
)
def sync_inventory_levels(self, item_numbers: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Sync BC item inventory -> Shopify inventory levels by SKU.
    - Matches on Shopify Variant SKU == BC Item Number (or reversed via SKU_MAP_JSON)
    - Uses SHOPIFY_LOCATION_ID if provided, otherwise first active location
    """
    with INVENTORY_SYNC_LATENCY.time():
        bc = BC365Client()
        shop = ShopifyClient()
        source = "bc_to_shopify"

        rev_map = _reverse_sku_map()  # BC -> Shopify
        loc_id = shop.resolve_location_id()
        if not loc_id:
            raise RuntimeError("No Shopify location available. Set SHOPIFY_LOCATION_ID or create an active location.")

        updated, failed = 0, 0
        items = _bc_iter_items(bc, only_numbers=item_numbers)

        for it in items:
            bc_no = str(it.get("number"))
            # Fall back to same value when no map
            sku = rev_map.get(bc_no, bc_no)

            INVENTORY_UPDATES_ATTEMPTED.labels(source=source).inc()
            try:
                v = shop.find_variant_by_sku(sku)
                if not v:
                    log.warning("shopify_variant_not_found", sku=sku, bc_number=bc_no)
                    INVENTORY_UPDATES_FAILED.labels(source=source).inc()
                    failed += 1
                    continue

                inv_item_id = int(v["inventory_item_id"])
                qty = int(float(it.get("inventory", 0) or 0))

                # Time each Shopify update
                with inventory_update_seconds.time():
                    shop.set_inventory_level(inv_item_id, int(loc_id), qty)

                shopify_inventory_updates_total.inc()
                log.info("inventory_set", sku=sku, bc_number=bc_no, location_id=loc_id, qty=qty)

                INVENTORY_UPDATES_SUCCEEDED.labels(source=source).inc()
                updated += 1

            except requests.HTTPError as e:
                log.error(
                    "inventory_update_http_error",
                    sku=sku,
                    bc_number=bc_no,
                    status=getattr(e.response, "status_code", None),
                    body=getattr(e.response, "text", None),
                )
                # Let Celery retry via autoretry_for
                raise
            except Exception:
                log.exception("inventory_update_error", sku=sku, bc_number=bc_no)
                INVENTORY_UPDATES_FAILED.labels(source=source).inc()
                failed += 1

        return {"attempted": len(items), "updated": updated, "failed": failed}


@shared_task(
    bind=True,
    autoretry_for=(RetryableHTTPError, requests.HTTPError),
    retry_kwargs={"max_retries": 3, "countdown": 10},
    # (optional but nice) give it a stable, explicit name:
    name="app.tasks.inventory.set_inventory_for_sku",
)
def set_inventory_for_sku(self, sku: str, available: int, location_id: int | None = None) -> dict:
    """
    Set a single variant's available inventory in Shopify for a given SKU.
    """
    s = ShopifyClient()
    v = s.find_variant_by_sku(sku)
    if not v:
        return {"sku": sku, "status": "variant_not_found"}

    loc_id = location_id or s.resolve_location_id()
    if not loc_id:
        raise ValueError("No location found. Set SHOPIFY_LOCATION_ID or create a location.")

    inv_item_id = int(v["inventory_item_id"])

    try:
        with inventory_update_seconds.time():
            resp = s.set_inventory_level(inv_item_id, int(loc_id), int(available))

        shopify_inventory_updates_total.inc()

        return {
            "sku": sku,
            "inventory_item_id": inv_item_id,
            "location_id": int(loc_id),
            "available": int(available),
            "shopify_response": resp,
        }
    except requests.HTTPError:
        # Allow Celery retry via autoretry_for
        raise
