# app/api/routers/debug_celery.py
from fastapi import APIRouter

from app.api.celery_app import celery_app

router = APIRouter(prefix="/debug/celery", tags=["debug: celery"])

@router.get("/tasks")
def list_tasks():
    insp = celery_app.control.inspect()
    return {
        "registered": insp.registered(),  # per-worker dict of registered task names
        "active_queues": insp.active_queues(),
    }
