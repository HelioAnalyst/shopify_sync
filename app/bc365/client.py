# app/bc365/client.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import time
import requests
from urllib.parse import quote
from app.core.config import settings

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}  # key: tenant|client_id -> (token, exp)

def _get_token() -> str:
    key = f"{settings.BC365_TENANT_ID}|{settings.BC365_CLIENT_ID}"
    tok = _TOKEN_CACHE.get(key)
    now = time.time()
    if tok and tok[1] - 60 > now:
        return tok[0]
    url = f"https://login.microsoftonline.com/{settings.BC365_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.BC365_CLIENT_ID,
        "client_secret": settings.BC365_CLIENT_SECRET,
        "scope": "https://api.businesscentral.dynamics.com/.default",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    access_token: str = j["access_token"]
    expires_in: int = int(j.get("expires_in", 3600))
    _TOKEN_CACHE[key] = (access_token, now + expires_in)
    return access_token

class BC365Client:
    def __init__(self):
        base_uri = "https://api.businesscentral.dynamics.com"
        env = (settings.BC365_ENVIRONMENT or "production").strip("/")
        self.base = f"{base_uri}/v2.0/{env}/api/v2.0"
        self._company_id_cache: Optional[str] = settings.BC365_COMPANY_ID or None

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}

    # --- Company helpers ---
    def list_companies(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/companies"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("value", [])

    def resolve_company_id(self) -> str:
        if self._company_id_cache:
            return self._company_id_cache
        name = (settings.BC365_COMPANY_NAME or "").strip()
        companies = self.list_companies()
        if not companies:
            raise RuntimeError("No companies returned from BC365 API")
        if name:
            for c in companies:
                if c.get("name") == name:
                    self._company_id_cache = c["id"]
                    return self._company_id_cache
            raise RuntimeError(f"Company '{name}' not found; available: {[c.get('name') for c in companies]}")
        # fallback: first company
        self._company_id_cache = companies[0]["id"]
        return self._company_id_cache

    # --- Items / products (API v2.0) ---
    def fetch_products(self) -> List[Dict[str, Any]]:
        cid = self.resolve_company_id()
        url = f"{self.base}/companies({cid})/items"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("value", [])

    def find_item_by_number(self, number: str) -> dict | None:
        """Find item by its 'number' (matches Shopify SKU in our mapping)."""
        cid = self.resolve_company_id()
        filt = f"number eq '{number}'"
        url = f"{self.base}/companies({cid})/items?$filter={quote(filt, safe='= ')}"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        items = r.json().get("value", [])
        return items[0] if items else None

    # --- Sales orders ---
    def push_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        cid = self.resolve_company_id()
        url = f"{self.base}/companies({cid})/salesOrders"
        r = requests.post(url, json=order, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()


    def find_sales_order_by_external_no(self, ext_no: str) -> dict | None:
        """Look up a sales order by externalDocumentNumber (trim to BC's 35-char limit)."""
        if not ext_no:
            return None
        ext_no = str(ext_no)[:35]                   # BC field limit
        ext_odata = ext_no.replace("'", "''")       # OData escape single quotes

        cid = self.resolve_company_id()             # <-- use resolver, not self.company_id
        url = f"{self.base}/companies({cid})/salesOrders"
        r = requests.get(
            url,
            headers=self._headers(),
            params={"$filter": f"externalDocumentNumber eq '{ext_odata}'"},
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("value", [])
        return items[0] if items else None