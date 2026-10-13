from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.domain.budget_models import Bucket
from app.domain.enums import CategoryKind, IncomeKind, Pot, TransactionType
from app.schemas.common import (
    CorrectionConfirmation,
    Instant,
    Name,
    OptionalText,
    PositiveCents,
    Schema,
    ShortText,
)


class CategoryRef(Schema):
    id: int
    name: str
    kind: CategoryKind
    color: str | None


class TransactionOut(Schema):
    id: int
    type: TransactionType
    occurred_at: datetime
    amount_cents: int
    bucket: Bucket | None
    category: CategoryRef | None
    description: str
    merchant: str | None
    period_id: int | None
    recurring_expense_id: int | None
    is_recurring: bool
    income_kind: IncomeKind | None
    income_target: Pot | None
    transfer_from: Pot | None
    transfer_to: Pot | None
    reversed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransactionListOut(Schema):
    items: list[TransactionOut]
    total: int
    expense_sum_cents: int
    income_sum_cents: int


SortField = Literal["occurred_at", "amount_cents", "description", "created_at"]


class ExpenseIn(CorrectionConfirmation):
    occurred_at: Instant
    amount_cents: PositiveCents
    category_id: int
    description: ShortText
    merchant: Name | None = None
    recurring_expense_id: int | None = None
    is_recurring: bool = False


class TransactionUpdate(CorrectionConfirmation):
    """Expenses accept every field. Incomes and transfers only accept the text fields;
    money movements of those are cancelled (storniert) and booked again."""

    occurred_at: Instant | None = None
    amount_cents: PositiveCents | None = None
    category_id: int | None = None
    description: ShortText | None = None
    merchant: Name | None = None
    is_recurring: bool | None = None


class IncomeIn(CorrectionConfirmation):
    occurred_at: Instant
    amount_cents: PositiveCents
    category_id: int | None = None
    description: ShortText
    target: Pot
    bucket: Literal[Bucket.LEISURE, Bucket.FIXED] = Bucket.LEISURE


class TransferIn(Schema):
    from_pot: Pot
    to_pot: Pot
    amount_cents: PositiveCents
    bucket: Literal[Bucket.LEISURE, Bucket.FIXED] | None = None
    savings_goal_id: int | None = Field(
        default=None, description="Bei Entnahme aus dem Sparen zuerst von diesem Sparziel lösen"
    )
    note: OptionalText = None

    @model_validator(mode="after")
    def _check(self) -> "TransferIn":
        if self.from_pot == self.to_pot:
            raise ValueError("Quelle und Ziel müssen verschieden sein")
        if Pot.PERIOD in (self.from_pot, self.to_pot) and self.bucket is None:
            raise ValueError("Für Umbuchungen mit dem Budget muss ein Topf gewählt werden")
        return self


class ReverseIn(CorrectionConfirmation):
    pass


class RecurringSuggestionOut(Schema):
    label: str
    merchant: str | None
    category: CategoryRef | None
    typical_amount_cents: int
    occurrences: int
    periods: int
    transaction_ids: list[int]
