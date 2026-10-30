from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UpdatedAt, UTCDateTime, str_enum
from app.domain.enums import AccountEntryKind, AccountKind


class Account(Base):
    """A place where money lies: a bank account, a brokerage depot, cash.

    Accounts say *where* the savings are, savings goals say *what for*. Neither
    creates money: the sum over all accounts never exceeds the savings balance.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("savings_share_bp >= 0 AND savings_share_bp <= 10000", name="share_in_range"),
        CheckConstraint("color_index >= 0", name="color_index_non_negative"),
        # The reserve lies in at most one place.
        Index(
            "uq_accounts_holds_reserve", "holds_reserve", unique=True, sqlite_where=text("holds_reserve = 1")
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    institution: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind, "account_kind"))
    # Fixed at creation so an account keeps its color when others are added or archived.
    color_index: Mapped[int] = mapped_column(default=0)
    # Share of every new savings rate that is booked here automatically (basis points).
    savings_share_bp: Mapped[int] = mapped_column(default=0)
    holds_reserve: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class AccountEntry(Base):
    """Append-only ledger of savings money per account."""

    __tablename__ = "account_entries"
    __table_args__ = (
        CheckConstraint("amount_cents != 0", name="amount_non_zero"),
        # The automatic split of a salary happens once per period and account.
        Index(
            "uq_account_entries_auto_split",
            "period_id",
            "account_id",
            unique=True,
            sqlite_where=text("kind = 'auto_split'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount_cents: Mapped[int]
    kind: Mapped[AccountEntryKind] = mapped_column(str_enum(AccountEntryKind, "account_entry_kind"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("budget_periods.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[CreatedAt]


class AccountValuation(Base):
    """A market value the user read off a depot or wallet.

    ``booked_cents`` is the money booked to the account at that moment, so the
    gain of a valuation stays fixed even when money is added later.
    """

    __tablename__ = "account_valuations"
    __table_args__ = (CheckConstraint("value_cents >= 0", name="value_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    value_cents: Mapped[int]
    booked_cents: Mapped[int]
    valued_at: Mapped[datetime] = mapped_column(UTCDateTime)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[CreatedAt]
