from fastapi import Header, HTTPException, status
from app.core.config import settings

async def require_admin_token(authorization: str = Header("")):
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = authorization[len(prefix):]
    if token != settings.ADMIN_API_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
