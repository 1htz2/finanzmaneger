"""Append-only ledgers. A balance is the sum of its rows; rows are never edited."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.db.base import Base, UTCDateTime, str_enum
from app.domain.enums import ReserveKind, SavingsKind


class ReserveEntry(Base):
    """The reserve is a virtual pot, not a bank account."""

    __tablename__ = "reserve_entries"
    __table_args__ = (
        CheckConstraint("amount_cents != 0", name="amount_non_zero"),
        # One automatic close-out credit per period, guaranteed by the DB.
        Index(
            "uq_reserve_entries_period_close",
            "period_id",
            unique=True,
            sqlite_where=text("kind = 'period_close'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    amount_cents: Mapped[int]
    kind: Mapped[ReserveKind] = mapped_column(str_enum(ReserveKind, "reserve_kind"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    purpose: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default)


class SavingsEntry(Base):
    __tablename__ = "savings_entries"
    __table_args__ = (
        CheckConstraint("amount_cents != 0", name="amount_non_zero"),
        Index(
            "uq_savings_entries_period_savings",
            "period_id",
            unique=True,
            sqlite_where=text("kind = 'period_savings'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    amount_cents: Mapped[int]
    kind: Mapped[SavingsKind] = mapped_column(str_enum(SavingsKind, "savings_kind"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default)


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    __table_args__ = (CheckConstraint("target_cents > 0", name="target_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    target_cents: Mapped[int]
    target_date: Mapped[date | None] = mapped_column(Date)
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default, onupdate=clock.now_default)


class SavingsAllocation(Base):
    """Earmarks part of the savings balance for a goal. Not additional money."""

    __tablename__ = "savings_allocations"
    __table_args__ = (CheckConstraint("amount_cents != 0", name="amount_non_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("savings_goals.id"), index=True)
    amount_cents: Mapped[int]
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=clock.now_default)
