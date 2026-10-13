from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.db.base import Base, UTCDateTime
from app.domain.budget_models import DEFAULT_BUDGET_MODEL

DEFAULT_RESERVE_PURPOSES = [
    "Unerwartete Rechnungen",
    "Einkommensschwache Monate",
    "Reparaturen",
    "Notfälle",
]


class AppSettings(Base):
    """Exactly one row (id = 1)."""

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("reserve_minimum_cents >= 0", name="reserve_minimum_non_negative"),
        CheckConstraint("large_expense_threshold_cents > 0", name="large_expense_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    budget_model_key: Mapped[str] = mapped_column(String(32), default=DEFAULT_BUDGET_MODEL)
    reserve_minimum_cents: Mapped[int] = mapped_column(default=0)
    large_expense_threshold_cents: Mapped[int] = mapped_column(default=15_000)
    reserve_purposes: Mapped[list[str]] = mapped_column(JSON, default=lambda: list(DEFAULT_RESERVE_PURPOSES))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default, onupdate=clock.now_default)
