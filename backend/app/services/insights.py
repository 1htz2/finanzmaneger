"""Read models for the dashboard and the statistics page."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.domain.budget_models import Bucket
from app.domain.closing import BucketStatus
from app.domain.enums import PeriodStatus, TransactionType
from app.domain.money import basis_points
from app.domain.pacing import compute_leisure_pace
from app.domain.warnings import LargeExpense, WarningContext, evaluate_warnings
from app.models import Category, Transaction
from app.schemas.misc import (
    CategoryBreakdownItem,
    CategoryBreakdownOut,
    DashboardOut,
    PaceOut,
    SavingsSummaryOut,
    StatsAveragesOut,
    StatsOverviewOut,
    WarningOut,
)
from app.schemas.periods import PeriodSummaryOut
from app.schemas.transactions import CategoryRef
from app.services import ledgers, pots, recurring
from app.services.periods import active_period, list_periods, summarize
from app.services.settings import get_app_settings
from app.services.transactions import list_transactions


def _status(summary: PeriodSummaryOut, bucket: Bucket) -> BucketStatus:
    b = next(x for x in summary.buckets if x.bucket == bucket)
    return BucketStatus(bucket=bucket, budget=b.budget_cents, spent=b.spent_cents)


def dashboard(db: Session) -> DashboardOut:
    period = active_period(db)
    settings = get_app_settings(db)
    reserve = ledgers.reserve_balance(db)
    balance, allocated = ledgers.savings_balance(db), ledgers.savings_allocated(db)
    ov = recurring.overview(db)
    periods = list_periods(db)

    summary = summarize(db, period) if period else None
    pace_out: PaceOut | None = None
    pace_reason: str | None = "no_active_period"
    warnings: list[WarningOut] = []
    if period is not None and summary is not None:
        leisure = _status(summary, Bucket.LEISURE)
        pace = None
        if period.expected_next_payday is None:
            pace_reason = "no_expected_payday"
        else:
            pace = compute_leisure_pace(
                budget=leisure.budget,
                spent=leisure.spent,
                period_start=clock.local_date(period.started_at),
                today=clock.today(),
                expected_payday=period.expected_next_payday,
            )
            pace_reason = None if pace else "payday_passed"
            if pace:
                pace_out = PaceOut(
                    days_left=pace.days_left,
                    per_day_cents=pace.per_day,
                    per_week_cents=pace.per_week,
                    planned_spent_by_today_cents=pace.planned_spent_by_today,
                    ahead_of_plan_by_cents=pace.ahead_of_plan_by,
                    expected_next_payday=period.expected_next_payday,
                )
        large = db.scalars(
            select(Transaction)
            .where(
                Transaction.period_id == period.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.recurring_expense_id.is_(None),
                Transaction.amount_cents >= settings.large_expense_threshold_cents,
            )
            .order_by(Transaction.amount_cents.desc())
            .limit(3)
        ).unique()
        ctx = WarningContext(
            leisure=leisure,
            fixed=_status(summary, Bucket.FIXED),
            fixed_open_planned=ov.open_in_period_cents,
            reserve_balance=reserve,
            reserve_minimum=settings.reserve_minimum_cents,
            large_expenses=[LargeExpense(t.description, t.amount_cents) for t in large],
            pace=pace,
        )
        warnings = [WarningOut.model_validate(w.__dict__) for w in evaluate_warnings(ctx)]

    return DashboardOut(
        active_period=summary,
        reserve_balance_cents=reserve,
        savings=SavingsSummaryOut(
            balance_cents=balance, allocated_cents=allocated, unallocated_cents=balance - allocated
        ),
        leisure_pace=pace_out,
        pace_unavailable_reason=pace_reason,  # type: ignore[arg-type]
        warnings=warnings,
        recent_transactions=list_transactions(db, limit=6).items,
        upcoming_fixed_costs=recurring.upcoming_costs(ov),
        fixed_open_cents=ov.open_in_period_cents,
        goals=pots.list_goals(db)[:4],
        reserve_history=pots.reserve_history(db)[-30:],
        period_comparison=list(reversed(periods[:6])),
    )


def _local_bounds(day_from: date | None, day_to: date | None) -> tuple[datetime | None, datetime | None]:
    start = clock.as_utc(datetime.combine(day_from, time.min)) if day_from else None
    end = clock.as_utc(datetime.combine(day_to + timedelta(days=1), time.min)) if day_to else None
    return start, end


def category_breakdown(
    db: Session,
    *,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    bucket: Bucket | None = None,
) -> CategoryBreakdownOut:
    stmt = (
        select(Transaction.category_id, func.sum(Transaction.amount_cents), func.count())
        .where(Transaction.type == TransactionType.EXPENSE)
        .group_by(Transaction.category_id)
    )
    if period_id is not None:
        stmt = stmt.where(Transaction.period_id == period_id)
    start, end = _local_bounds(date_from, date_to)
    if start:
        stmt = stmt.where(Transaction.occurred_at >= start)
    if end:
        stmt = stmt.where(Transaction.occurred_at < end)
    if bucket is not None:
        stmt = stmt.where(Transaction.bucket == bucket)
    rows = db.execute(stmt).all()
    total = sum(r[1] for r in rows)
    categories = {c.id: c for c in db.scalars(select(Category))}
    items = [
        CategoryBreakdownItem(
            category=CategoryRef.model_validate(categories[cid]) if cid in categories else None,
            total_cents=amount,
            count=count,
            share_bp=basis_points(amount, total),
        )
        for cid, amount, count in rows
    ]
    return CategoryBreakdownOut(items=sorted(items, key=lambda i: -i.total_cents), total_cents=total)


def _avg(values: list[int]) -> int | None:
    return sum(values) // len(values) if values else None


def stats_overview(db: Session, limit: int = 24) -> StatsOverviewOut:
    periods = list(reversed(list_periods(db)[:limit]))
    closed = [p for p in periods if p.status == PeriodStatus.CLOSED]

    def spent(p: PeriodSummaryOut, bucket: Bucket) -> int:
        return next(b.spent_cents for b in p.buckets if b.bucket == bucket)

    rates = [p.actual_savings_rate_bp for p in closed if p.actual_savings_rate_bp is not None]
    planned = periods[-1].planned_savings_rate_bp if periods else 2000
    return StatsOverviewOut(
        periods=periods,
        averages=StatsAveragesOut(
            closed_periods=len(closed),
            avg_income_cents=_avg([p.net_salary_cents + p.extra_income_cents for p in closed]),
            avg_fixed_spent_cents=_avg([spent(p, Bucket.FIXED) for p in closed]),
            avg_leisure_spent_cents=_avg([spent(p, Bucket.LEISURE) for p in closed]),
            avg_actual_savings_rate_bp=_avg(rates),
            planned_savings_rate_bp=planned,
        ),
        reserve_history=pots.reserve_history(db),
        savings_history=pots.savings_history(db),
    )
