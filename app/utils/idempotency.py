from hashlib import sha256
from app.core.db import SessionLocal, IdempotencyKey

def key_for(payload: bytes) -> str:
    return sha256(payload).hexdigest()

def ensure_once(key: str, note: str = "") -> bool:
    with SessionLocal() as s:
        existing = s.get(IdempotencyKey, key)
        if existing:
            return False
        s.add(IdempotencyKey(key=key, note=note))
        s.commit()
        return True
