from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UpdatedAt


class Debt(Base):
    """Money the user owes. The remaining amount is never stored: it is the opening
    balance minus every expense booked as a repayment of this debt."""

    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("original_cents > 0", name="original_positive"),
        CheckConstraint(
            "opening_balance_cents >= 0 AND opening_balance_cents <= original_cents",
            name="opening_balance_in_range",
        ),
        CheckConstraint("monthly_rate_cents IS NULL OR monthly_rate_cents > 0", name="rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    creditor: Mapped[str | None] = mapped_column(String(128))
    original_cents: Mapped[int]
    # Still owed when the debt was entered; lets users add a loan they have been paying for years.
    opening_balance_cents: Mapped[int]
    monthly_rate_cents: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(String(500))
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
