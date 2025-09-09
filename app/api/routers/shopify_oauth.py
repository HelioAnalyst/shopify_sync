import hashlib, hmac, urllib.parse, secrets, requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from app.core.config import settings
from app.core.db import save_shop_token
from app.shopify.webhooks import register_default_webhooks

router = APIRouter(prefix="/oauth")
_NONCE = {}  # dev-only

def _verify_hmac(query_params: dict, secret: str) -> bool:
    qp = {k: v for k, v in query_params.items() if k != "hmac"}
    message = "&".join(f"{k}={v}" for k, v in sorted(qp.items()))
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, query_params.get("hmac", ""))

@router.get("/install")
def install(shop: str):
    if not (settings.SHOPIFY_CLIENT_ID and settings.APP_BASE_URL):
        raise HTTPException(500, "OAuth not configured")
    state = secrets.token_urlsafe(16)
    _NONCE[state] = True
    scopes = settings.OAUTH_SCOPES
    redirect_uri = f"{settings.APP_BASE_URL.rstrip('/')}/oauth/callback"
    url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={settings.SHOPIFY_CLIENT_ID}"
        f"&scope={urllib.parse.quote(scopes)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={state}"
    )
    return RedirectResponse(url)

@router.get("/callback")
def callback(request: Request):
    params = dict(request.query_params)
    shop = params.get("shop")
    state = params.get("state")
    code = params.get("code")
    if not shop or not code or state not in _NONCE:
        raise HTTPException(400, "Invalid OAuth response")
    del _NONCE[state]

    if not _verify_hmac(params, settings.SHOPIFY_CLIENT_SECRET or ""):
        raise HTTPException(401, "Invalid HMAC")

    token_url = f"https://{shop}/admin/oauth/access_token"
    resp = requests.post(token_url, json={
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
        "code": code,
    }, timeout=30)
    resp.raise_for_status()
    access_token = resp.json().get("access_token")
    if not access_token:
        raise HTTPException(500, "No access_token in response")

    save_shop_token(shop, access_token)
    register_default_webhooks(
        shop_domain=shop,
        access_token=access_token,
        public_base=settings.APP_BASE_URL or "",
        api_version=settings.SHOPIFY_API_VERSION,
    )
    return HTMLResponse(f"<h2>Installed for {shop}</h2><p>Webhooks registered.</p>")
