from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UpdatedAt, str_enum
from app.domain.recurring import Interval
from app.models.category import Category


class RecurringExpense(Base):
    """A planned fixed cost. Planning only: it never counts as spending by itself."""

    __tablename__ = "recurring_expenses"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    amount_cents: Mapped[int]
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    interval: Mapped[Interval] = mapped_column(str_enum(Interval, "interval"))
    due_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    category: Mapped[Category] = relationship(lazy="joined")
