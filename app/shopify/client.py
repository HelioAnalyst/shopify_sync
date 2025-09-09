# app/shopify/client.py
import time
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any, List
import requests

from app.core.config import settings
from app.utils.retry import retry_policy, RetryableHTTPError


class ShopifyClient:
    """
    Minimal Shopify Admin API client with:
      - Token or basic-auth (legacy) support
      - Light rate-limit backoff using X-Shopify-Shop-Api-Call-Limit
      - Retry policy for 429/5xx via @retry_policy
    """

    def __init__(self, access_token: Optional[str] = None, shop_domain: Optional[str] = None) -> None:
        self.shop = (shop_domain or settings.SHOPIFY_SHOP).rstrip("/")
        self.version = settings.SHOPIFY_API_VERSION
        self.base = f"https://{self.shop}/admin/api/{self.version}"
        self.session = requests.Session()

        # Prefer a real Admin API access token (custom app: shpat_...)
        token = access_token or settings.SHOPIFY_ACCESS_TOKEN

        if token:
            # Token-based auth (recommended)
            self.session.headers.update({
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
            })
        elif settings.SHOPIFY_API_KEY and settings.SHOPIFY_API_PASSWORD:
            # Legacy private app style basic auth
            self.session.auth = (settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_PASSWORD)
            self.session.headers.update({"Content-Type": "application/json"})
        else:
            raise ValueError(
                "Missing Shopify credentials. Set SHOPIFY_ACCESS_TOKEN (Admin API access token) "
                "or SHOPIFY_API_KEY+SHOPIFY_API_PASSWORD for legacy private-app basic auth."
            )

    # ---------- low-level helpers ----------

    def _maybe_throttle(self, resp: requests.Response) -> None:
        """If we’re >80% of the bucket, sleep a bit to avoid hitting 429s."""
        limit = resp.headers.get("X-Shopify-Shop-Api-Call-Limit")
        if not limit:
            return
        try:
            used, bucket = map(int, limit.split("/"))
            if bucket and (used / bucket) > 0.80:
                time.sleep(0.5)
        except Exception:
            pass

    @retry_policy
    def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Retry for 429/5xx and apply light throttling. Returns parsed JSON or {}."""
        url = f"{self.base}{path}"
        resp = self.session.request(method, url, timeout=30, **kwargs)
        self._maybe_throttle(resp)
        if resp.status_code in (429, 500, 502, 503):
            raise RetryableHTTPError(f"{resp.status_code}: {resp.text}")
        resp.raise_for_status()
        return resp.json() if (resp.text or "").strip() else {}

    # ---------- common ops ----------

    def create_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "/products.json", json={"product": payload})

    def update_product(self, product_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("PUT", f"/products/{product_id}.json", json={"product": payload})

    def find_variant_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        data = self.request("GET", "/variants.json", params={"sku": sku})
        variants = data.get("variants", [])
        return variants[0] if variants else None

    def list_locations(self) -> List[Dict[str, Any]]:
        data = self.request("GET", "/locations.json")
        return data.get("locations", [])

    def resolve_location_id(self) -> Optional[int]:
        if settings.SHOPIFY_LOCATION_ID:
            try:
                return int(str(settings.SHOPIFY_LOCATION_ID).strip())
            except ValueError:
                pass
        locs = self.list_locations()
        return int(locs[0]["id"]) if locs else None
        
    def get_inventory_level(self, inventory_item_id: int, location_id: int) -> Optional[int]:
        data = self.request("GET", "/inventory_levels.json",
                            params={"inventory_item_ids": int(inventory_item_id), "location_ids": int(location_id)})
        levels = data.get("inventory_levels", [])
        return int(levels[0]["available"]) if levels else None




    def set_inventory_level(self, inventory_item_id: int, location_id: int, available: int) -> Dict[str, Any]:
        return self.request(
            "POST",
            "/inventory_levels/set.json",
            json={
                "inventory_item_id": int(inventory_item_id),
                "location_id": int(location_id),
                "available": int(available),
            },
        )

    # ---------- webhook HMAC verify ----------

    @staticmethod
    def verify_webhook(hmac_header: str, body: bytes) -> bool:
        secret = (settings.SHOPIFY_WEBHOOK_SECRET or "").encode()
        digest = hmac.new(secret, body, hashlib.sha256).digest()
        computed = base64.b64encode(digest).decode()
        return hmac.compare_digest(computed, hmac_header)
