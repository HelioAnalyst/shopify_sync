from sqlalchemy import create_engine, text, String, Integer
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    detail: Mapped[str] = mapped_column(String(2048), default="")

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    note: Mapped[str] = mapped_column(String(256), default="")

class Shop(Base):
    __tablename__ = "shops"
    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    access_token: Mapped[str] = mapped_column(String(255))

def save_shop_token(domain: str, token: str) -> None:
    with SessionLocal() as s:
        row = s.get(Shop, domain)
        if row:
            row.access_token = token
        else:
            s.add(Shop(domain=domain, access_token=token))
        s.commit()

def get_shop_token(domain: str) -> str | None:
    with SessionLocal() as s:
        row = s.get(Shop, domain)
        return row.access_token if row else None

Base.metadata.create_all(engine)

def db_healthcheck() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
