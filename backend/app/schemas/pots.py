from datetime import date, datetime

from pydantic import Field

from app.domain.enums import ReserveKind, SavingsKind
from app.schemas.common import (
    MAX_CENTS,
    Instant,
    Name,
    NonNegativeCents,
    OptionalText,
    PositiveCents,
    Schema,
    ShortText,
)


class BalancePoint(Schema):
    at: datetime
    balance_cents: int


class ReserveEntryOut(Schema):
    id: int
    amount_cents: int
    kind: ReserveKind
    occurred_at: datetime
    period_id: int | None
    transaction_id: int | None
    purpose: str | None
    note: str | None
    created_at: datetime


class ReserveOut(Schema):
    balance_cents: int
    minimum_cents: int
    purposes: list[str]
    entries: list[ReserveEntryOut]
    history: list[BalancePoint]
    total_from_periods_cents: int
    total_withdrawn_cents: int
    # Fixed + leisure budget of the latest period: what one month of living costs, for target suggestions.
    monthly_spending_cents: int | None


class ReserveDepositIn(Schema):
    amount_cents: PositiveCents
    note: ShortText
    occurred_at: Instant | None = None


class ReserveSetupIn(Schema):
    target_cents: PositiveCents
    starting_cents: NonNegativeCents = 0


class ReserveWithdrawIn(Schema):
    amount_cents: PositiveCents
    purpose: Name
    reason: ShortText
    occurred_at: Instant | None = None


class SavingsEntryOut(Schema):
    id: int
    amount_cents: int
    kind: SavingsKind
    occurred_at: datetime
    period_id: int | None
    transaction_id: int | None
    note: str | None
    created_at: datetime


class GoalOut(Schema):
    id: int
    title: str
    target_cents: int
    target_date: date | None
    archived: bool
    saved_cents: int
    remaining_cents: int
    progress_bp: int
    projected_date: date | None
    required_per_month_cents: int | None
    created_at: datetime


class SavingsOut(Schema):
    balance_cents: int
    allocated_cents: int
    unallocated_cents: int
    entries: list[SavingsEntryOut]
    goals: list[GoalOut]
    history: list[BalancePoint]


class GoalIn(Schema):
    title: Name
    target_cents: PositiveCents
    target_date: date | None = None


class GoalUpdate(Schema):
    title: Name | None = None
    target_cents: PositiveCents | None = None
    target_date: date | None = None
    archived: bool | None = None


class GoalAllocateIn(Schema):
    amount_cents: int = Field(
        ge=-MAX_CENTS, le=MAX_CENTS, description="Positiv: zuweisen. Negativ: freigeben."
    )
    note: OptionalText = None


class SavingsWithdrawIn(Schema):
    amount_cents: PositiveCents
    reason: ShortText
    goal_id: int | None = None
    account_id: int | None = None
