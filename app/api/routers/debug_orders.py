from fastapi import APIRouter
from uuid import uuid4
from app.tasks.orders import push_order_to_bc365

router = APIRouter(prefix="/debug")

@router.post("/orders/test")
def enqueue_test_order(sku: str = "1896-S", qty: int = 1, price: float = 98.00, ext: str | None = None):
    ext_no = (ext or uuid4().hex)[:35]  # <= 35 chars for BC
    payload = {
        "id": ext_no,
        "line_items": [{"sku": sku, "quantity": qty, "price": f"{price:.2f}"}],
    }
    push_order_to_bc365.delay(payload)
    return {"queued": True, "id": ext_no, "sku": sku, "qty": qty}
