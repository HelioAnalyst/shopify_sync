from typing import Dict, Any
import structlog
from celery import shared_task
from app.shopify.client import ShopifyClient
from app.bc365.client import BC365Client
from app.utils.chunk import chunked

log = structlog.get_logger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=30, retry_jitter=True)
def bulk_upsert_products(self) -> Dict[str, Any]:
    bc = BC365Client()
    shop = ShopifyClient()

    products = bc.fetch_products()
    total = len(products)
    updated = 0

    for batch in chunked(products, 100):
        for p in batch:
            payload = map_bc_to_shopify(p)
            product_id = payload.get("id")
            try:
                if product_id:
                    shop.update_product(product_id, payload)
                else:
                    shop.create_product(payload)
                updated += 1
            except Exception as e:
                log.warning("product_upsert_failed", sku=p.get("No"), error=str(e))
                raise
    log.info("bulk_upsert_done", total=total, updated=updated)
    return {"total": total, "updated": updated}

def map_bc_to_shopify(p: Dict[str, Any]) -> Dict[str, Any]:
    sku = p.get("No") or "SKU"
    title = p.get("Description") or sku
    price = p.get("Unit_Price", "0.00")
    if isinstance(price, (int, float)):
        price = f"{price:.2f}"
    return {"title": title, "variants": [{"sku": sku, "price": price}], "status": "active"}
