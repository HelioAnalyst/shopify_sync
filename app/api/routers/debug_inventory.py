# app/api/routers/debug_inventory.py
from fastapi import APIRouter, HTTPException, Query

from app.shopify.client import ShopifyClient
from app.metrics.prom import inventory_update_seconds, shopify_inventory_updates_total
from app.tasks.inventory import set_inventory_for_sku  # Celery task

router = APIRouter(prefix="/debug/inventory", tags=["debug: inventory"])


@router.get("/variant")
def variant_lookup(sku: str = Query(..., description="Variant SKU")):
    s = ShopifyClient()
    v = s.find_variant_by_sku(sku)
    if not v:
        raise HTTPException(404, detail=f"Variant with sku '{sku}' not found")
    return {"sku": sku, "variant": v}


@router.get("/locations")
def list_locations():
    s = ShopifyClient()
    return {"locations": s.list_locations()}


@router.api_route("/set", methods=["GET", "POST"])
def set_inventory(
    sku: str = Query(..., description="Variant SKU"),
    available: int = Query(..., ge=0, description="New available qty"),
    location_id: int | None = Query(None, description="Override location id"),
):
    s = ShopifyClient()
    v = s.find_variant_by_sku(sku)
    if not v:
        raise HTTPException(404, detail=f"Variant with sku '{sku}' not found")

    loc_id = location_id or s.resolve_location_id()
    if not loc_id:
        raise HTTPException(400, detail="No location found. Set SHOPIFY_LOCATION_ID or create a location.")

    inv_item_id = int(v["inventory_item_id"])

    # Metrics timing wrapper
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


@router.get("/level")
def get_level(
    sku: str = Query(..., description="Variant SKU"),
    location_id: int | None = Query(None, description="Override location id"),
):
    s = ShopifyClient()
    v = s.find_variant_by_sku(sku)
    if not v:
        raise HTTPException(404, detail=f"Variant with sku '{sku}' not found")

    loc_id = location_id or s.resolve_location_id()
    if not loc_id:
        raise HTTPException(400, detail="No location found. Set SHOPIFY_LOCATION_ID or create a location.")

    data = s.request(
        "GET",
        "/inventory_levels.json",
        params={"inventory_item_ids": v["inventory_item_id"], "location_ids": loc_id},
    )
    levels = data.get("inventory_levels", [])
    return {"sku": sku, "location_id": int(loc_id), "levels": levels}


@router.post("/queue")
def queue_inventory_update(
    sku: str = Query(...),
    available: int = Query(..., ge=0),
    location_id: int | None = Query(None),
):
    # Fire-and-forget task; worker logs the result
    set_inventory_for_sku.delay(sku=sku, available=available, location_id=location_id)
    return {"queued": True, "sku": sku, "available": int(available), "location_id": location_id}
