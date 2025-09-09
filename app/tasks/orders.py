from typing import Dict, Any, List
import structlog, json, requests
from celery import shared_task
from app.bc365.client import BC365Client
from app.core.config import settings
from app.metrics.prom import ORDERS_PUSHED, ORDERS_DEDUPED, ORDER_PUSH_LATENCY

log = structlog.get_logger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(requests.HTTPError,),
    retry_backoff=True, retry_backoff_max=30, retry_jitter=True
)
def push_order_to_bc365(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
    bc = BC365Client()

    raw_ext = str(order_payload.get("id", ""))
    ext_no = raw_ext[:35] if raw_ext else ""        # <-- trim BEFORE find
    if ext_no:
        existing = bc.find_sales_order_by_external_no(ext_no)
        if existing:
            ORDERS_DEDUPED.inc()
            log.info("order_already_exists",
                    bc_id=existing.get("id"), bc_no=existing.get("number"), ext_no=ext_no)
            return {"bc_id": existing.get("id"), "bc_no": existing.get("number"), "deduped": True}

    body = _map_shopify_to_bc(order_payload, bc, ext_no=ext_no)

    with ORDER_PUSH_LATENCY.time():
        result = bc.push_order(body)
    ORDERS_PUSHED.inc()

    log.info("order_pushed",
             shopify_id=order_payload.get("id"),
             bc_id=result.get("id"), bc_no=result.get("number"))
    return {"bc_id": result.get("id"), "bc_no": result.get("number")}

def _map_shopify_to_bc(order: Dict[str, Any], bc: BC365Client, *, ext_no: str) -> Dict[str, Any]:
    cust_no = settings.BC365_DEFAULT_CUSTOMER or "10000"

    sku_map = {}
    if settings.SKU_MAP_JSON:
        try:
            sku_map = json.loads(settings.SKU_MAP_JSON)
            log.info("sku_map_loaded", sku_map=sku_map)
        except Exception:
            pass

    lines: List[Dict[str, Any]] = []
    for li in order.get("line_items", []):
        raw_sku = li.get("sku") or (li.get("variant_id") and str(li["variant_id"])) or (li.get("product_id") and str(li["product_id"]))
        if not raw_sku:
            continue
        sku = sku_map.get(raw_sku, raw_sku)

        item = bc.find_item_by_number(sku)
        if not item:
            log.warning("bc_item_not_found", sku=raw_sku, mapped_to=sku, title=li.get("title"))
            continue

        qty = li.get("quantity", 1) or 1
        try:
            unit_price_f = float(li.get("price")) if li.get("price") is not None else None
        except Exception:
            unit_price_f = None

        line = {"lineType": "Item", "itemId": item["id"], "quantity": qty}
        if unit_price_f is not None:
            line["unitPrice"] = unit_price_f
        lines.append(line)

    if not lines:
        raise ValueError("No lines could be mapped to BC items (check SKUs match BC item numbers).")

    # Use the same trimmed value for the body
    return {
        "customerNumber": cust_no,
        "externalDocumentNumber": ext_no,       # use trimmed value consistently
        "salesOrderLines": lines,
    }
