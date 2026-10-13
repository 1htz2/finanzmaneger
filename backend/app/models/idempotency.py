from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.db.base import Base, UTCDateTime


class IdempotencyKey(Base):
    """Stored response of a mutating request, keyed by the client's Idempotency-Key."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    scope: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int]
    response: Mapped[object] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default)
