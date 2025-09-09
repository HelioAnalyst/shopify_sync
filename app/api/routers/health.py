from fastapi import APIRouter
from app.core.db import db_healthcheck

router = APIRouter()

@router.get("/health")
def health():
    db_healthcheck()
    return {"status": "ok"}
