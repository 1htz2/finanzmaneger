"""Balances of the reserve and savings pots. Always sums over the ledgers."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ReserveKind, SavingsKind
from app.models import ReserveEntry, SavingsAllocation, SavingsEntry


def reserve_balance(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(ReserveEntry.amount_cents), 0))) or 0


def savings_balance(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(SavingsEntry.amount_cents), 0))) or 0


def savings_allocated(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(SavingsAllocation.amount_cents), 0))) or 0


def savings_unallocated(db: Session) -> int:
    return savings_balance(db) - savings_allocated(db)


def book_reserve(
    db: Session,
    amount: int,
    kind: ReserveKind,
    occurred_at: datetime,
    *,
    period_id: int | None = None,
    transaction_id: int | None = None,
    purpose: str | None = None,
    note: str | None = None,
) -> ReserveEntry | None:
    if amount == 0:
        return None
    entry = ReserveEntry(
        amount_cents=amount,
        kind=kind,
        occurred_at=occurred_at,
        period_id=period_id,
        transaction_id=transaction_id,
        purpose=purpose,
        note=note,
    )
    db.add(entry)
    return entry


def book_savings(
    db: Session,
    amount: int,
    kind: SavingsKind,
    occurred_at: datetime,
    *,
    period_id: int | None = None,
    transaction_id: int | None = None,
    note: str | None = None,
) -> SavingsEntry | None:
    if amount == 0:
        return None
    entry = SavingsEntry(
        amount_cents=amount,
        kind=kind,
        occurred_at=occurred_at,
        period_id=period_id,
        transaction_id=transaction_id,
        note=note,
    )
    db.add(entry)
    return entry
