# app/api/routers/debug_webhooks.py
from fastapi import APIRouter, HTTPException, Query
from app.core.db import get_shop_token
from app.core.config import settings
from app.shopify.client import ShopifyClient
from app.shopify.webhooks import register_default_webhooks

router = APIRouter(prefix="/debug")

@router.get("/webhooks")
def list_webhooks(shop: str = Query(..., description="shop domain, e.g. teststorebase-200.myshopify.com")):
    token = get_shop_token(shop)
    if not token:
        raise HTTPException(404, f"No access token saved for {shop}. Install the app first.")
    client = ShopifyClient(access_token=token, shop_domain=shop)
    data = client.request("GET", "/webhooks.json")
    return {"shop": shop, "count": len(data.get("webhooks", [])), "webhooks": data.get("webhooks", [])}

@router.post("/webhooks/ensure")
def ensure_webhooks(shop: str = Query(..., description="shop domain")):
    token = get_shop_token(shop)
    if not token:
        raise HTTPException(404, f"No access token saved for {shop}. Install the app first.")
    if not settings.APP_BASE_URL:
        raise HTTPException(500, "APP_BASE_URL not set in .env")

    register_default_webhooks(
        shop_domain=shop,
        access_token=token,
        public_base=settings.APP_BASE_URL,
        api_version=settings.SHOPIFY_API_VERSION,
    )
    return {"ok": True, "shop": shop, "address": f"{settings.APP_BASE_URL.rstrip('/')}/webhooks/shopify"}
