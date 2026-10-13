"""Planned fixed costs versus actually booked fixed costs.

A planned cost only becomes spending when the user books it (``pay``), which
creates an expense linked to the plan. Open = expected occurrences minus linked
payments, so a booked payment is never counted twice.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import DomainValidationError, NotFoundError
from app.domain.budget_models import Bucket
from app.domain.enums import CategoryKind, TransactionType
from app.domain.money import basis_points
from app.domain.recurring import (
    INTERVAL_MONTHS,
    Interval,
    add_months,
    monthly_equivalent,
    occurrences,
)
from app.models import BudgetPeriod, Category, RecurringExpense, Transaction
from app.schemas.misc import UpcomingCostOut
from app.schemas.recurring import (
    PayRecurringIn,
    RecurringIn,
    RecurringOut,
    RecurringOverviewOut,
    RecurringPlanItem,
    RecurringUpdate,
)
from app.schemas.transactions import CategoryRef, ExpenseIn, TransactionOut
from app.services.periods import active_period, bucket_statuses
from app.services.transactions import create_expense


def to_out(r: RecurringExpense) -> RecurringOut:
    return RecurringOut(
        id=r.id,
        name=r.name,
        amount_cents=r.amount_cents,
        category=CategoryRef.model_validate(r.category),
        interval=r.interval,
        due_date=r.due_date,
        active=r.active,
        description=r.description,
        monthly_equivalent_cents=monthly_equivalent(r.amount_cents, r.interval),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _get(db: Session, rid: int) -> RecurringExpense:
    r = db.get(RecurringExpense, rid)
    if r is None:
        raise NotFoundError("Fixkosten-Eintrag nicht gefunden")
    return r


def _check_category(db: Session, category_id: int) -> None:
    category = db.get(Category, category_id)
    if category is None or category.kind != CategoryKind.FIXED:
        raise DomainValidationError("Bitte eine Fixkosten-Kategorie wählen.")


def list_recurring(db: Session) -> list[RecurringOut]:
    rows = db.scalars(
        select(RecurringExpense).order_by(RecurringExpense.active.desc(), RecurringExpense.name)
    ).unique()
    return [to_out(r) for r in rows]


def create_recurring(db: Session, data: RecurringIn) -> RecurringOut:
    _check_category(db, data.category_id)
    r = RecurringExpense(**data.model_dump())
    db.add(r)
    db.flush()
    db.refresh(r)
    return to_out(r)


def update_recurring(db: Session, rid: int, data: RecurringUpdate) -> RecurringOut:
    r = _get(db, rid)
    fields = data.model_dump(exclude_unset=True)
    if fields.pop("clear_due_date", False):
        r.due_date = None
        fields.pop("due_date", None)
    if fields.get("category_id") is not None:
        _check_category(db, fields["category_id"])
    for key, value in fields.items():
        if value is not None or key == "description":
            setattr(r, key, value)
    db.flush()
    db.refresh(r)
    return to_out(r)


def delete_recurring(db: Session, rid: int) -> None:
    """Booked payments stay as expenses; only their link to the plan is removed."""
    db.delete(_get(db, rid))
    db.flush()


def pay_recurring(db: Session, rid: int, data: PayRecurringIn) -> TransactionOut:
    r = _get(db, rid)
    return create_expense(
        db,
        ExpenseIn(
            occurred_at=data.occurred_at or clock.now(),
            amount_cents=data.amount_cents or r.amount_cents,
            category_id=r.category_id,
            description=r.name,
            recurring_expense_id=r.id,
            is_recurring=True,
            confirm_correction=data.confirm_correction,
            correction_reason=data.correction_reason,
        ),
    )


def _window(period: BudgetPeriod) -> tuple[date, date, bool]:
    start = clock.local_date(period.started_at)
    if period.expected_next_payday:
        return start, period.expected_next_payday, False
    return start, add_months(start, 1), True


def _expected_dates(r: RecurringExpense, start: date, end: date) -> tuple[list[date], int]:
    """Due dates in the window and how many payments are expected.

    A monthly cost without due date is expected once per period. Quarterly or
    yearly costs without due date cannot be placed and are only shown as a
    monthly share.
    """
    if r.due_date is not None:
        dates = occurrences(r.due_date, r.interval, start, end)
        return dates, len(dates)
    return [], 1 if r.interval == Interval.MONTHLY else 0


def _next_due(r: RecurringExpense, today: date) -> date | None:
    if r.due_date is None:
        return None
    upcoming = occurrences(r.due_date, r.interval, today, today + timedelta(days=370))
    return upcoming[0] if upcoming else None


def overview(db: Session) -> RecurringOverviewOut:
    period = active_period(db)
    rows = list(db.scalars(select(RecurringExpense).where(RecurringExpense.active.is_(True))).unique())
    today = clock.today()
    monthly_total = sum(monthly_equivalent(r.amount_cents, r.interval) for r in rows)
    yearly_total = sum(r.amount_cents * 12 // INTERVAL_MONTHS[r.interval] for r in rows)

    if period is None:
        return RecurringOverviewOut(
            has_active_period=False,
            window_start=None,
            window_end=None,
            window_estimated=False,
            items=[
                RecurringPlanItem(
                    expense=to_out(r),
                    due_dates=[],
                    paid_count=0,
                    paid_cents=0,
                    open_count=0,
                    open_cents=0,
                    next_due_date=_next_due(r, today),
                )
                for r in rows
            ],
            monthly_total_cents=monthly_total,
            yearly_total_cents=yearly_total,
            planned_in_period_cents=0,
            paid_in_period_cents=0,
            open_in_period_cents=0,
            fixed_budget_cents=0,
            fixed_spent_cents=0,
            planned_share_bp=None,
            sufficient=True,
            shortfall_cents=0,
        )

    start, end, estimated = _window(period)
    paid = {
        rid: (count, total)
        for rid, count, total in db.execute(
            select(
                Transaction.recurring_expense_id,
                func.count(),
                func.sum(Transaction.amount_cents),
            )
            .where(
                Transaction.period_id == period.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.recurring_expense_id.is_not(None),
            )
            .group_by(Transaction.recurring_expense_id)
        ).all()
    }
    items: list[RecurringPlanItem] = []
    for r in rows:
        dates, expected = _expected_dates(r, start, end)
        paid_count, paid_cents = paid.get(r.id, (0, 0))
        open_count = max(expected - paid_count, 0)
        items.append(
            RecurringPlanItem(
                expense=to_out(r),
                due_dates=dates,
                paid_count=paid_count,
                paid_cents=paid_cents,
                open_count=open_count,
                open_cents=open_count * r.amount_cents,
                next_due_date=_next_due(r, today),
            )
        )
    items.sort(key=lambda i: (i.open_count == 0, i.next_due_date or date.max))
    fixed = bucket_statuses(db, period.id)[Bucket.FIXED]
    planned = sum((i.paid_count + i.open_count) * i.expense.amount_cents for i in items)
    open_total = sum(i.open_cents for i in items)
    needed = fixed.spent + open_total
    return RecurringOverviewOut(
        has_active_period=True,
        window_start=start,
        window_end=end,
        window_estimated=estimated,
        items=items,
        monthly_total_cents=monthly_total,
        yearly_total_cents=yearly_total,
        planned_in_period_cents=planned,
        paid_in_period_cents=sum(i.paid_cents for i in items),
        open_in_period_cents=open_total,
        fixed_budget_cents=fixed.budget,
        fixed_spent_cents=fixed.spent,
        planned_share_bp=basis_points(planned, fixed.budget),
        sufficient=needed <= fixed.budget,
        shortfall_cents=max(needed - fixed.budget, 0),
    )


def upcoming_costs(ov: RecurringOverviewOut, limit: int = 5) -> list[UpcomingCostOut]:
    """Still-open due dates of the current window (latest open occurrences)."""
    result: list[UpcomingCostOut] = []
    for item in ov.items:
        if item.open_count == 0:
            continue
        dates = item.due_dates[-item.open_count :] if item.due_dates else []
        if not dates and item.next_due_date:
            dates = [item.next_due_date]
        for due in dates or ([ov.window_end] if ov.window_end else []):
            result.append(
                UpcomingCostOut(
                    recurring_expense_id=item.expense.id,
                    name=item.expense.name,
                    amount_cents=item.expense.amount_cents,
                    due_date=due,
                    category=item.expense.category,
                )
            )
    return sorted(result, key=lambda u: u.due_date)[:limit]
