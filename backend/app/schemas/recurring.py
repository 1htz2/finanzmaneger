from datetime import date, datetime

from app.domain.recurring import Interval
from app.schemas.common import (
    CorrectionConfirmation,
    Instant,
    Name,
    OptionalText,
    PositiveCents,
    Schema,
)
from app.schemas.transactions import CategoryRef


class RecurringIn(Schema):
    name: Name
    amount_cents: PositiveCents
    category_id: int
    interval: Interval
    due_date: date | None = None
    active: bool = True
    description: OptionalText = None


class RecurringUpdate(Schema):
    name: Name | None = None
    amount_cents: PositiveCents | None = None
    category_id: int | None = None
    interval: Interval | None = None
    due_date: date | None = None
    clear_due_date: bool = False
    active: bool | None = None
    description: OptionalText = None


class RecurringOut(Schema):
    id: int
    name: str
    amount_cents: int
    category: CategoryRef
    interval: Interval
    due_date: date | None
    active: bool
    description: str | None
    debt_id: int | None
    monthly_equivalent_cents: int
    created_at: datetime
    updated_at: datetime


class RecurringPlanItem(Schema):
    expense: RecurringOut
    due_dates: list[date]
    paid_count: int
    paid_cents: int
    open_count: int
    open_cents: int
    next_due_date: date | None


class RecurringOverviewOut(Schema):
    has_active_period: bool
    window_start: date | None
    window_end: date | None
    window_estimated: bool
    items: list[RecurringPlanItem]
    monthly_total_cents: int
    yearly_total_cents: int
    planned_in_period_cents: int
    paid_in_period_cents: int
    open_in_period_cents: int
    fixed_budget_cents: int
    fixed_spent_cents: int
    planned_share_bp: int | None
    sufficient: bool
    shortfall_cents: int


class PayRecurringIn(CorrectionConfirmation):
    occurred_at: Instant | None = None
    amount_cents: PositiveCents | None = None
