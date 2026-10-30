from datetime import date, datetime
from typing import Literal

from pydantic import model_validator

from app.schemas.common import Name, NonNegativeCents, OptionalText, PositiveCents, Schema


class DebtIn(Schema):
    name: Name
    creditor: Name | None = None
    original_cents: PositiveCents
    # What is still owed today. Defaults to the full amount for a new debt.
    opening_balance_cents: NonNegativeCents | None = None
    monthly_rate_cents: PositiveCents | None = None
    note: OptionalText = None
    # Also create a monthly fixed cost for the instalment, so it shows up in the plan.
    plan_rate: bool = False
    rate_category_id: int | None = None
    rate_due_date: date | None = None

    @model_validator(mode="after")
    def _check(self) -> "DebtIn":
        if self.opening_balance_cents is not None and self.opening_balance_cents > self.original_cents:
            raise ValueError("Die Restschuld kann nicht höher sein als der ursprüngliche Betrag")
        if self.plan_rate and self.monthly_rate_cents is None:
            raise ValueError("Zum Einplanen wird eine monatliche Rate benötigt")
        return self


class DebtUpdate(Schema):
    name: Name | None = None
    creditor: Name | None = None
    original_cents: PositiveCents | None = None
    opening_balance_cents: NonNegativeCents | None = None
    monthly_rate_cents: PositiveCents | None = None
    note: OptionalText = None
    archived: bool | None = None


class DebtOut(Schema):
    id: int
    name: str
    creditor: str | None
    original_cents: int
    opening_balance_cents: int
    monthly_rate_cents: int | None
    note: str | None
    archived: bool
    status: Literal["open", "paid_off"]
    repaid_cents: int
    remaining_cents: int
    progress_bp: int
    repayment_count: int
    last_repayment_at: datetime | None
    projected_payoff: date | None
    planned_recurring_ids: list[int]
    created_at: datetime
    updated_at: datetime


class DebtsOverviewOut(Schema):
    items: list[DebtOut]
    total_remaining_cents: int
    total_original_cents: int
    total_monthly_rate_cents: int
    repaid_this_period_cents: int
