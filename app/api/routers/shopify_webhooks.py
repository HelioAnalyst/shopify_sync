from fastapi import APIRouter, Request, Header, HTTPException
from app.shopify.client import ShopifyClient
from app.tasks.orders import push_order_to_bc365
from app.metrics.prom import WEBHOOKS_RECEIVED

router = APIRouter(prefix="/webhooks")

@router.post("/shopify")
async def shopify_webhook(request: Request, x_shopify_hmac_sha256: str = Header(None)):
    body = await request.body()
    if not ShopifyClient.verify_webhook(x_shopify_hmac_sha256 or "", body):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    event = request.headers.get("X-Shopify-Topic", "unknown")
    WEBHOOKS_RECEIVED.labels(topic=event).inc()   # <-- here

    payload = await request.json()
    if event == "orders/create":
        push_order_to_bc365.delay(payload)
    return {"ok": True}
