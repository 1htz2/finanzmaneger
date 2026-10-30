from datetime import datetime
from typing import Annotated

from pydantic import Field, model_validator

from app.domain.enums import AccountEntryKind, AccountKind
from app.schemas.common import MAX_CENTS, Name, NonNegativeCents, PositiveCents, Schema, ShortText
from app.schemas.pots import BalancePoint

ShareBp = Annotated[int, Field(ge=0, le=10_000)]


class AccountIn(Schema):
    name: Name
    institution: Name | None = None
    kind: AccountKind
    savings_share_bp: ShareBp = 0
    holds_reserve: bool = False


class AccountUpdate(Schema):
    name: Name | None = None
    institution: Name | None = None
    kind: AccountKind | None = None
    holds_reserve: bool | None = None
    archived: bool | None = None


class ShareIn(Schema):
    account_id: int
    share_bp: ShareBp


class SharesIn(Schema):
    """Replaces the whole split. Accounts that are not listed get 0 %."""

    shares: list[ShareIn] = Field(max_length=50)

    @model_validator(mode="after")
    def _check(self) -> "SharesIn":
        if sum(s.share_bp for s in self.shares) > 10_000:
            raise ValueError("Die Anteile ergeben zusammen mehr als 100 %")
        if len({s.account_id for s in self.shares}) != len(self.shares):
            raise ValueError("Jeder Anlageort darf nur einmal vorkommen")
        return self


class AssignIn(Schema):
    """Positive: unassigned savings go to the account. Negative: back to unassigned."""

    amount_cents: int = Field(ge=-MAX_CENTS, le=MAX_CENTS)
    note: ShortText | None = None


class MoveIn(Schema):
    from_account_id: int
    to_account_id: int
    amount_cents: PositiveCents
    note: ShortText | None = None

    @model_validator(mode="after")
    def _check(self) -> "MoveIn":
        if self.from_account_id == self.to_account_id:
            raise ValueError("Quelle und Ziel müssen verschieden sein")
        return self


class ValuationIn(Schema):
    value_cents: NonNegativeCents
    note: ShortText | None = None


class ValuationOut(Schema):
    id: int
    value_cents: int
    booked_cents: int
    valued_at: datetime
    note: str | None


class AccountEntryOut(Schema):
    id: int
    account_id: int
    amount_cents: int
    kind: AccountEntryKind
    occurred_at: datetime
    period_id: int | None
    transaction_id: int | None
    note: str | None


class AccountOut(Schema):
    id: int
    name: str
    institution: str | None
    kind: AccountKind
    color_index: int
    savings_share_bp: int
    holds_reserve: bool
    archived: bool
    # Savings money booked here.
    booked_cents: int
    # Gain or loss since the last valuation; 0 without valuation.
    gain_cents: int
    gain_bp: int | None
    value_cents: int
    last_valued_at: datetime | None
    # The reserve balance when the reserve lies here, else 0.
    reserve_cents: int
    total_cents: int
    valuations: list[ValuationOut]
    created_at: datetime


class GroupTotal(Schema):
    label: str
    total_cents: int
    account_ids: list[int]


class WealthOut(Schema):
    accounts: list[AccountOut]
    savings_balance_cents: int
    unassigned_cents: int
    reserve_cents: int
    reserve_account_id: int | None
    gains_cents: int
    total_assets_cents: int
    debt_cents: int
    net_worth_cents: int
    shares_total_bp: int
    institutions: list[GroupTotal]
    entries: list[AccountEntryOut]
    history: list[BalancePoint]
