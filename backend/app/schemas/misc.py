from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.domain.budget_models import Bucket
from app.domain.enums import CategoryKind
from app.domain.warnings import Severity
from app.schemas.common import Name, NonNegativeCents, PositiveCents, Schema
from app.schemas.periods import PeriodSummaryOut
from app.schemas.pots import BalancePoint, GoalOut
from app.schemas.transactions import CategoryRef, TransactionOut

Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]


class CategoryOut(Schema):
    id: int
    name: str
    kind: CategoryKind
    color: str | None
    is_default: bool
    archived: bool
    usage_count: int = 0


class CategoryIn(Schema):
    name: Name
    kind: CategoryKind
    color: Color | None = None


class CategoryUpdate(Schema):
    name: Name | None = None
    color: Color | None = None
    archived: bool | None = None


class BudgetModelOut(Schema):
    key: str
    label: str
    shares_percent: dict[Bucket, int]


class SettingsOut(Schema):
    budget_model_key: str
    budget_models: list[BudgetModelOut]
    reserve_minimum_cents: int
    large_expense_threshold_cents: int
    reserve_purposes: list[str]
    currency: Literal["EUR"] = "EUR"
    timezone: Literal["Europe/Berlin"] = "Europe/Berlin"


class SettingsUpdate(Schema):
    budget_model_key: str | None = None
    reserve_minimum_cents: NonNegativeCents | None = None
    large_expense_threshold_cents: PositiveCents | None = None
    reserve_purposes: list[Name] | None = Field(default=None, max_length=30)


class WarningOut(Schema):
    code: str
    severity: Severity
    title: str
    message: str


class PaceOut(Schema):
    days_left: int
    per_day_cents: int
    per_week_cents: int
    planned_spent_by_today_cents: int
    ahead_of_plan_by_cents: int
    expected_next_payday: date


class UpcomingCostOut(Schema):
    recurring_expense_id: int
    name: str
    amount_cents: int
    due_date: date
    category: CategoryRef


class SavingsSummaryOut(Schema):
    balance_cents: int
    allocated_cents: int
    unallocated_cents: int


class DashboardOut(Schema):
    active_period: PeriodSummaryOut | None
    reserve_balance_cents: int
    savings: SavingsSummaryOut
    leisure_pace: PaceOut | None
    pace_unavailable_reason: Literal["no_active_period", "no_expected_payday", "payday_passed"] | None
    warnings: list[WarningOut]
    recent_transactions: list[TransactionOut]
    upcoming_fixed_costs: list[UpcomingCostOut]
    fixed_open_cents: int
    goals: list[GoalOut]
    reserve_history: list[BalancePoint]
    period_comparison: list[PeriodSummaryOut]


class CategoryBreakdownItem(Schema):
    category: CategoryRef | None
    total_cents: int
    count: int
    share_bp: int | None


class CategoryBreakdownOut(Schema):
    items: list[CategoryBreakdownItem]
    total_cents: int


class StatsAveragesOut(Schema):
    closed_periods: int
    avg_income_cents: int | None
    avg_fixed_spent_cents: int | None
    avg_leisure_spent_cents: int | None
    avg_actual_savings_rate_bp: int | None
    planned_savings_rate_bp: int


class StatsOverviewOut(Schema):
    periods: list[PeriodSummaryOut]
    averages: StatsAveragesOut
    reserve_history: list[BalancePoint]
    savings_history: list[BalancePoint]
