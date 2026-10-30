"""Where the savings lie. Accounts hold parts of the savings balance; the rest is
"unassigned". Every booking is a row in ``account_entries`` and two invariants hold
after every write: no account is below zero, and all accounts together never hold
more than the savings balance."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.domain.enums import AccountEntryKind
from app.domain.money import basis_points, format_eur, split_weighted
from app.models import Account, AccountEntry, AccountValuation
from app.schemas.accounts import (
    AccountIn,
    AccountOut,
    AccountUpdate,
    AssignIn,
    MoveIn,
    SharesIn,
    ValuationIn,
    ValuationOut,
)
from app.services import ledgers

PALETTE_SIZE = 8


def get_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise NotFoundError("Anlageort nicht gefunden")
    return account


def booked_balances(db: Session) -> dict[int, int]:
    return dict(
        db.execute(
            select(AccountEntry.account_id, func.sum(AccountEntry.amount_cents)).group_by(
                AccountEntry.account_id
            )
        ).all()
    )


def unassigned(db: Session) -> int:
    return ledgers.savings_balance(db) - sum(booked_balances(db).values())


def check_invariants(db: Session) -> None:
    """Called after every write that lowers savings or moves money between accounts."""
    db.flush()
    balances = booked_balances(db)
    for account_id, balance in balances.items():
        if balance < 0:
            account = get_account(db, account_id)
            raise DomainValidationError(
                f"Auf „{account.name}“ liegen dafür nicht genug Ersparnisse.",
                code="account_insufficient",
            )
    free = ledgers.savings_balance(db) - sum(balances.values())
    if free < 0:
        raise DomainValidationError(
            "Dieses Geld ist bereits Anlageorten zugeordnet. Wähle, von welchem Anlageort es kommt.",
            code="savings_location_insufficient",
        )


def book(
    db: Session,
    account_id: int,
    amount: int,
    kind: AccountEntryKind,
    at: datetime | None = None,
    *,
    period_id: int | None = None,
    transaction_id: int | None = None,
    note: str | None = None,
) -> AccountEntry | None:
    if amount == 0:
        return None
    account = get_account(db, account_id)
    if amount > 0 and account.archived:
        raise DomainValidationError(f"„{account.name}“ ist archiviert.")
    entry = AccountEntry(
        account_id=account_id,
        amount_cents=amount,
        kind=kind,
        occurred_at=at or clock.now(),
        period_id=period_id,
        transaction_id=transaction_id,
        note=note[:255] if note else None,
    )
    db.add(entry)
    return entry


# ------------------------------------------------------------ salary split


def auto_split(db: Session, period_id: int, savings_cents: int, at: datetime) -> None:
    """Books the shares of a new savings rate. What no account claims stays unassigned."""
    accounts = db.scalars(
        select(Account).where(Account.archived.is_(False), Account.savings_share_bp > 0).order_by(Account.id)
    ).all()
    if not accounts or savings_cents <= 0:
        return
    weights: dict[int | None, int] = {a.id: a.savings_share_bp for a in accounts}
    weights[None] = 10_000 - sum(weights.values())
    for account_id, amount in split_weighted(savings_cents, weights).items():
        if account_id is not None:
            book(
                db, account_id, amount, AccountEntryKind.AUTO_SPLIT, at, period_id=period_id, note="Sparrate"
            )


def adjust_salary_split(db: Session, period_id: int, old_savings: int, new_savings: int) -> None:
    """A corrected salary changes the savings rate; the accounts keep their proportion of it."""
    rows = db.execute(
        select(AccountEntry.account_id, func.sum(AccountEntry.amount_cents))
        .where(
            AccountEntry.period_id == period_id,
            AccountEntry.kind.in_([AccountEntryKind.AUTO_SPLIT, AccountEntryKind.SALARY_CORRECTION]),
        )
        .group_by(AccountEntry.account_id)
        .order_by(AccountEntry.account_id)
    ).all()
    current: dict[int, int] = {account_id: amount for account_id, amount in rows if amount}
    if not current or old_savings <= 0:
        return
    weights: dict[int | None, int] = {k: v for k, v in current.items()}
    weights[None] = max(old_savings - sum(current.values()), 0)
    target = split_weighted(new_savings, weights)
    for account_id, amount in current.items():
        book(
            db,
            account_id,
            target[account_id] - amount,
            AccountEntryKind.SALARY_CORRECTION,
            period_id=period_id,
            note="Gehaltskorrektur",
        )


# ------------------------------------------------------------ accounts


def _valuations(db: Session, account_id: int) -> list[AccountValuation]:
    return list(
        db.scalars(
            select(AccountValuation)
            .where(AccountValuation.account_id == account_id)
            .order_by(AccountValuation.valued_at.desc(), AccountValuation.id.desc())
        )
    )


def account_out(db: Session, account: Account, booked: int, reserve: int) -> AccountOut:
    valuations = _valuations(db, account.id)
    gain = valuations[0].value_cents - valuations[0].booked_cents if valuations else 0
    value = max(booked + gain, 0)
    reserve_here = reserve if account.holds_reserve else 0
    return AccountOut(
        id=account.id,
        name=account.name,
        institution=account.institution,
        kind=account.kind,
        color_index=account.color_index,
        savings_share_bp=account.savings_share_bp,
        holds_reserve=account.holds_reserve,
        archived=account.archived,
        booked_cents=booked,
        gain_cents=value - booked,
        gain_bp=basis_points(value - booked, booked) if valuations else None,
        value_cents=value,
        last_valued_at=valuations[0].valued_at if valuations else None,
        reserve_cents=reserve_here,
        total_cents=value + reserve_here,
        valuations=[ValuationOut.model_validate(v) for v in valuations[:24]],
        created_at=account.created_at,
    )


def get_account_out(db: Session, account_id: int) -> AccountOut:
    account = get_account(db, account_id)
    return account_out(db, account, booked_balances(db).get(account.id, 0), ledgers.reserve_balance(db))


def _hold_reserve(db: Session, account: Account) -> None:
    for other in db.scalars(select(Account).where(Account.holds_reserve.is_(True), Account.id != account.id)):
        other.holds_reserve = False
    db.flush()
    account.holds_reserve = True


def _check_share_total(db: Session) -> None:
    db.flush()
    total = db.scalar(
        select(func.coalesce(func.sum(Account.savings_share_bp), 0)).where(Account.archived.is_(False))
    )
    if (total or 0) > 10_000:
        raise DomainValidationError("Die Anteile der Sparrate ergeben zusammen mehr als 100 %.")


def create_account(db: Session, data: AccountIn) -> AccountOut:
    count = db.scalar(select(func.count()).select_from(Account)) or 0
    account = Account(
        name=data.name,
        institution=data.institution,
        kind=data.kind,
        color_index=count % PALETTE_SIZE,
        savings_share_bp=data.savings_share_bp,
    )
    db.add(account)
    db.flush()
    if data.holds_reserve:
        _hold_reserve(db, account)
    _check_share_total(db)
    return get_account_out(db, account.id)


def update_account(db: Session, account_id: int, data: AccountUpdate) -> AccountOut:
    account = get_account(db, account_id)
    fields = data.model_dump(exclude_unset=True)
    if "institution" in fields:
        account.institution = fields.pop("institution")
    if fields.get("archived") is True and not account.archived:
        booked = booked_balances(db).get(account.id, 0)
        if booked != 0:
            raise ConflictError(
                f"Auf „{account.name}“ liegen noch {format_eur(booked)}. Verschiebe das Geld zuerst.",
                code="account_not_empty",
            )
        account.savings_share_bp = 0
        account.holds_reserve = False
    holds_reserve = fields.pop("holds_reserve", None)
    for key, value in fields.items():
        if value is not None:
            setattr(account, key, value)
    if holds_reserve is True:
        if account.archived:
            raise DomainValidationError("Ein archivierter Anlageort kann die Reserve nicht aufnehmen.")
        _hold_reserve(db, account)
    elif holds_reserve is False:
        account.holds_reserve = False
    db.flush()
    return get_account_out(db, account.id)


def delete_account(db: Session, account_id: int) -> None:
    account = get_account(db, account_id)
    used = db.scalar(select(func.count()).where(AccountEntry.account_id == account.id)) or 0
    valued = db.scalar(select(func.count()).where(AccountValuation.account_id == account.id)) or 0
    if used or valued:
        raise ConflictError(
            "Dieser Anlageort hat schon Buchungen. Archiviere ihn stattdessen.", code="account_has_entries"
        )
    db.delete(account)
    db.flush()


def set_shares(db: Session, data: SharesIn) -> None:
    requested = {s.account_id: s.share_bp for s in data.shares}
    for account in db.scalars(select(Account)):
        share = requested.pop(account.id, 0)
        if share and account.archived:
            raise DomainValidationError(f"„{account.name}“ ist archiviert.")
        account.savings_share_bp = share
    if requested:
        raise NotFoundError("Anlageort nicht gefunden")
    _check_share_total(db)


def assign(db: Session, account_id: int, data: AssignIn) -> AccountOut:
    if data.amount_cents == 0:
        raise DomainValidationError("Der Betrag darf nicht 0 sein.")
    if data.amount_cents > 0:
        free = unassigned(db)
        if data.amount_cents > free:
            raise DomainValidationError(
                f"Es sind nur {format_eur(free)} Ersparnisse ohne Anlageort vorhanden.",
                code="savings_location_insufficient",
            )
    book(db, account_id, data.amount_cents, AccountEntryKind.ASSIGN, note=data.note)
    check_invariants(db)
    return get_account_out(db, account_id)


def move(db: Session, data: MoveIn) -> None:
    source, target = get_account(db, data.from_account_id), get_account(db, data.to_account_id)
    note = data.note or f"{source.name} → {target.name}"
    book(db, source.id, -data.amount_cents, AccountEntryKind.MOVE, note=note)
    book(db, target.id, data.amount_cents, AccountEntryKind.MOVE, note=note)
    check_invariants(db)


def add_valuation(db: Session, account_id: int, data: ValuationIn) -> AccountOut:
    account = get_account(db, account_id)
    if account.archived:
        raise DomainValidationError(f"„{account.name}“ ist archiviert.")
    db.add(
        AccountValuation(
            account_id=account.id,
            value_cents=data.value_cents,
            booked_cents=booked_balances(db).get(account.id, 0),
            valued_at=clock.now(),
            note=data.note,
        )
    )
    db.flush()
    return get_account_out(db, account.id)


def mirror_for_reversal(db: Session, transaction_id: int, note: str) -> None:
    """A cancelled income or transfer takes its money back out of the same accounts."""
    rows = db.scalars(select(AccountEntry).where(AccountEntry.transaction_id == transaction_id)).all()
    for row in rows:
        book(
            db,
            row.account_id,
            -row.amount_cents,
            AccountEntryKind.REVERSAL,
            transaction_id=transaction_id,
            note=note,
        )
