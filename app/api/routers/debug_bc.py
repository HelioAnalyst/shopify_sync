from fastapi import APIRouter
from app.bc365.client import BC365Client

router = APIRouter(prefix="/debug/bc")

@router.get("/companies")
def companies():
    bc = BC365Client()
    return bc.list_companies()

@router.get("/items")
def items():
    bc = BC365Client()
    return {"count": len(bc.fetch_products())}
