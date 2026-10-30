"""The whole picture: where savings and reserve lie, minus what is owed."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountEntry, ReserveEntry, SavingsEntry
from app.schemas.accounts import AccountEntryOut, GroupTotal, WealthOut
from app.schemas.pots import BalancePoint
from app.services import accounts, debts, ledgers

NO_INSTITUTION = "Ohne Bank"


def _history(db: Session) -> list[BalancePoint]:
    """Booked savings plus reserve over time. Market gains are not part of it,
    because valuations are snapshots, not a continuous price series."""
    rows = sorted(
        [(r.occurred_at, r.id, r.amount_cents) for r in db.scalars(select(SavingsEntry))]
        + [(r.occurred_at, r.id, r.amount_cents) for r in db.scalars(select(ReserveEntry))],
        key=lambda r: (r[0], r[1]),
    )
    total, points = 0, []
    for at, _, amount in rows:
        total += amount
        points.append(BalancePoint(at=at, balance_cents=total))
    return points


def overview(db: Session) -> WealthOut:
    booked = accounts.booked_balances(db)
    reserve = ledgers.reserve_balance(db)
    savings = ledgers.savings_balance(db)
    items = [
        accounts.account_out(db, a, booked.get(a.id, 0), reserve)
        for a in db.scalars(select(Account).order_by(Account.archived, Account.id))
    ]
    active = [a for a in items if not a.archived]
    holder = next((a for a in active if a.holds_reserve), None)
    gains = sum(a.gain_cents for a in active)

    groups: dict[str, list[int]] = defaultdict(list)
    totals: dict[str, int] = defaultdict(int)
    for a in active:
        label = a.institution or NO_INSTITUTION
        groups[label].append(a.id)
        totals[label] += a.total_cents
    institutions = sorted(
        (GroupTotal(label=k, total_cents=totals[k], account_ids=v) for k, v in groups.items()),
        key=lambda g: -g.total_cents,
    )

    total_assets = savings + gains + reserve
    debt = debts.overview(db).total_remaining_cents
    entries = db.scalars(
        select(AccountEntry).order_by(AccountEntry.occurred_at.desc(), AccountEntry.id.desc()).limit(60)
    )
    return WealthOut(
        accounts=items,
        savings_balance_cents=savings,
        unassigned_cents=savings - sum(booked.values()),
        reserve_cents=reserve,
        reserve_account_id=holder.id if holder else None,
        gains_cents=gains,
        total_assets_cents=total_assets,
        debt_cents=debt,
        net_worth_cents=total_assets - debt,
        shares_total_bp=sum(a.savings_share_bp for a in active),
        institutions=institutions,
        entries=[AccountEntryOut.model_validate(e) for e in entries],
        history=_history(db),
    )
