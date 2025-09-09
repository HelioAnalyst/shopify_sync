from typing import List
from app.shopify.client import ShopifyClient

DEFAULT_TOPICS: List[str] = [
    "orders/create",
    "products/update",
    "inventory_levels/update",
]

def register_default_webhooks(shop_domain: str, access_token: str, public_base: str, api_version: str) -> None:
    client = ShopifyClient(access_token=access_token, shop_domain=shop_domain)
    address = f"{public_base.rstrip('/')}/webhooks/shopify"
    for topic in DEFAULT_TOPICS:
        try:
            client.request("POST", "/webhooks.json",
                           json={"webhook": {"topic": topic, "address": address, "format": "json"}})
        except Exception:
            # ignore duplicate/422 errors for idempotency
            pass
