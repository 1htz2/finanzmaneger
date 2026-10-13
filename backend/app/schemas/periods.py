from datetime import date, datetime

from pydantic import Field

from app.domain.budget_models import Bucket
from app.domain.enums import AllocationSource, CorrectionAction, PeriodStatus
from app.schemas.common import Instant, OptionalText, PositiveCents, Schema, ShortText


class BucketStatusOut(Schema):
    bucket: Bucket
    budget_cents: int
    spent_cents: int
    available_cents: int
    used_bp: int | None


class AllocationOut(Schema):
    id: int
    bucket: Bucket
    amount_cents: int
    source: AllocationSource
    note: str | None
    created_at: datetime


class CorrectionOut(Schema):
    id: int
    period_id: int
    transaction_id: int | None
    action: CorrectionAction
    leftover_before_cents: int
    leftover_after_cents: int
    reserve_delta_cents: int
    reason: str
    created_at: datetime


class PeriodSummaryOut(Schema):
    id: int
    status: PeriodStatus
    started_at: datetime
    ended_at: datetime | None
    budget_model_key: str
    net_salary_cents: int
    extra_income_cents: int = Field(description="Weitere Einnahmen, die dieser Periode zugeordnet wurden")
    transfer_net_cents: int = Field(
        description="Saldo bewusster Umbuchungen zwischen Budget und Reserve/Sparen"
    )
    total_budget_cents: int
    expected_next_payday: date | None
    buckets: list[BucketStatusOut]
    spent_cents: int
    leftover_cents: int
    reserve_transfer_cents: int
    deficit_cents: int
    planned_savings_rate_bp: int
    actual_savings_rate_bp: int | None
    transaction_count: int


class PeriodDetailOut(PeriodSummaryOut):
    allocations: list[AllocationOut]
    corrections: list[CorrectionOut]


class SalaryPreviewIn(Schema):
    amount_cents: PositiveCents
    received_at: Instant


class SalaryIn(SalaryPreviewIn):
    description: OptionalText = None
    cover_deficit_from_reserve: bool = False
    expected_next_payday: date | None = None


class ClosingPreviewOut(Schema):
    period: PeriodSummaryOut
    leftover_cents: int
    reserve_transfer_cents: int
    deficit_cents: int
    coverable_from_reserve_cents: int
    transactions_moving_to_new_period: int


class SplitOut(Schema):
    bucket: Bucket
    percent: int
    amount_cents: int


class SalaryPreviewOut(Schema):
    closing: ClosingPreviewOut | None
    new_split: list[SplitOut]
    budget_model_label: str
    reserve_balance_before_cents: int
    reserve_balance_after_cents: int
    savings_balance_before_cents: int
    savings_balance_after_cents: int


class SalaryResultOut(Schema):
    closed_period: PeriodSummaryOut | None
    reserve_transfer_cents: int
    deficit_cents: int
    deficit_covered_cents: int
    new_period: PeriodSummaryOut
    reserve_balance_cents: int
    savings_balance_cents: int


class SalaryCorrectionIn(Schema):
    amount_cents: PositiveCents
    reason: ShortText


class ExpectedPaydayIn(Schema):
    expected_next_payday: date | None


class CoverDeficitIn(Schema):
    amount_cents: PositiveCents | None = None
    reason: OptionalText = None
