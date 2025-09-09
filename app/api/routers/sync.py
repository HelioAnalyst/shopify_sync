from fastapi import APIRouter, Depends
from app.api.dependencies import require_admin_token
from app.tasks.products import bulk_upsert_products
from app.tasks.inventory import sync_inventory_levels
from app.tasks.orders import push_order_to_bc365

router = APIRouter(prefix="/sync", dependencies=[Depends(require_admin_token)])

@router.post("/products/bulk")
def trigger_products_bulk():
    r = bulk_upsert_products.delay()
    return {"task_id": r.id}

@router.post("/inventory/locations")
def trigger_inventory_sync():
    r = sync_inventory_levels.delay([])  # supply real updates later
    return {"task_id": r.id}

@router.post("/orders/push")
def push_order_stub():
    r = push_order_to_bc365.delay({})
    return {"task_id": r.id}
