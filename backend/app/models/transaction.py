from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UpdatedAt, UTCDateTime, str_enum
from app.domain.budget_models import Bucket
from app.domain.enums import IncomeKind, Pot, TransactionType
from app.models.category import Category


class Transaction(Base):
    """Every money movement the user sees in the list.

    * expense: spending from the ``fixed`` or ``leisure`` bucket of a period.
    * income: ``salary`` opens a period; ``other`` goes to a pot chosen by the user.
    * transfer: moves money between pots and is neither income nor spending.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(
            "type != 'expense' OR (bucket IN ('fixed', 'leisure') AND period_id IS NOT NULL"
            " AND income_kind IS NULL AND transfer_from IS NULL)",
            name="expense_shape",
        ),
        CheckConstraint(
            "type != 'income' OR (income_kind IS NOT NULL AND income_target IS NOT NULL"
            " AND transfer_from IS NULL)",
            name="income_shape",
        ),
        CheckConstraint(
            "type != 'transfer' OR (transfer_from IS NOT NULL AND transfer_to IS NOT NULL"
            " AND transfer_from != transfer_to AND income_kind IS NULL)",
            name="transfer_shape",
        ),
        CheckConstraint("income_kind != 'salary' OR income_target = 'period'", name="salary_targets_period"),
        Index("ix_transactions_period_type", "period_id", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TransactionType] = mapped_column(str_enum(TransactionType, "txn_type"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    amount_cents: Mapped[int]
    bucket: Mapped[Bucket | None] = mapped_column(str_enum(Bucket, "txn_bucket"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    merchant: Mapped[str | None] = mapped_column(String(128))
    period_id: Mapped[int | None] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    recurring_expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_expenses.id", ondelete="SET NULL"), index=True
    )
    is_recurring: Mapped[bool] = mapped_column(default=False)
    income_kind: Mapped[IncomeKind | None] = mapped_column(str_enum(IncomeKind, "income_kind"))
    income_target: Mapped[Pot | None] = mapped_column(str_enum(Pot, "income_target"))
    transfer_from: Mapped[Pot | None] = mapped_column(str_enum(Pot, "transfer_from"))
    transfer_to: Mapped[Pot | None] = mapped_column(str_enum(Pot, "transfer_to"))
    reversed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Prepared for phase 2 imports (bank CSV, payslips); "manual" for everything in v1.
    source: Mapped[str] = mapped_column(String(32), default="manual")
    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    category: Mapped[Category | None] = relationship(lazy="joined")
