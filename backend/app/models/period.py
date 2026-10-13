from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UTCDateTime, str_enum
from app.domain.budget_models import Bucket
from app.domain.enums import AllocationSource, CorrectionAction, PeriodStatus


class BudgetPeriod(Base):
    """Runs from one salary receipt up to (excluding) the next one."""

    __tablename__ = "budget_periods"
    __table_args__ = (
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL AND closing_leftover_cents IS NULL)"
            " OR (status = 'closed' AND ended_at IS NOT NULL"
            " AND closing_leftover_cents IS NOT NULL AND ended_at > started_at)",
            name="status_consistency",
        ),
        CheckConstraint("net_salary_cents > 0", name="net_salary_positive"),
        # SQLite partial unique index: at most one active period, enforced by the DB.
        Index(
            "uq_budget_periods_single_active",
            "status",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, unique=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[PeriodStatus] = mapped_column(str_enum(PeriodStatus, "period_status"))
    budget_model_key: Mapped[str] = mapped_column(String(32))
    net_salary_cents: Mapped[int]
    expected_next_payday: Mapped[date | None] = mapped_column(Date)
    closing_leftover_cents: Mapped[int | None]
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[CreatedAt]

    allocations: Mapped[list["BudgetAllocation"]] = relationship(
        back_populates="period", order_by="BudgetAllocation.id"
    )


class BudgetAllocation(Base):
    """Money assigned to a bucket of a period. The bucket budget is the sum of its rows."""

    __tablename__ = "budget_allocations"
    __table_args__ = (CheckConstraint("amount_cents != 0", name="amount_non_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    bucket: Mapped[Bucket] = mapped_column(str_enum(Bucket, "bucket"))
    amount_cents: Mapped[int]
    source: Mapped[AllocationSource] = mapped_column(str_enum(AllocationSource, "alloc_source"))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[CreatedAt]

    period: Mapped[BudgetPeriod] = relationship(back_populates="allocations")


class PeriodCorrection(Base):
    """Audit record of every explicit change to a closed period's result."""

    __tablename__ = "period_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    action: Mapped[CorrectionAction] = mapped_column(str_enum(CorrectionAction, "corr_action"))
    leftover_before_cents: Mapped[int]
    leftover_after_cents: Mapped[int]
    reserve_delta_cents: Mapped[int]
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[CreatedAt]
