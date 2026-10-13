"""Expenses, other incomes, transfers and reversals.

Money never appears or disappears inside the app: every transfer books two legs
of equal size, and incomes or transfers are cancelled with mirrored rows.
"""

import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.domain.budget_models import Bucket
from app.domain.enums import (
    AllocationSource,
    CategoryKind,
    CorrectionAction,
    IncomeKind,
    Pot,
    ReserveKind,
    SavingsKind,
    TransactionType,
)
from app.domain.money import format_eur
from app.models import (
    BudgetAllocation,
    Category,
    RecurringExpense,
    ReserveEntry,
    SavingsAllocation,
    SavingsEntry,
    SavingsGoal,
    Transaction,
)
from app.schemas.transactions import (
    CategoryRef,
    ExpenseIn,
    IncomeIn,
    RecurringSuggestionOut,
    SortField,
    TransactionListOut,
    TransactionOut,
    TransactionUpdate,
    TransferIn,
)
from app.services import ledgers
from app.services.periods import (
    active_period,
    bucket_statuses,
    period_at,
    require_active_period,
    require_period_at,
    settle_closed_periods,
    snapshot_closed,
)

POT_LABELS = {Pot.PERIOD: "Budget", Pot.RESERVE: "Reserve", Pot.SAVINGS: "Sparen"}
BUCKET_LABELS = {Bucket.FIXED: "Fixkosten", Bucket.LEISURE: "Freizeit", Bucket.SAVINGS: "Sparen"}


def to_out(txn: Transaction) -> TransactionOut:
    return TransactionOut.model_validate(txn)


def get_transaction(db: Session, txn_id: int) -> Transaction:
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise NotFoundError("Buchung nicht gefunden")
    return txn


def _category(db: Session, category_id: int, kinds: set[CategoryKind]) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise DomainValidationError("Kategorie nicht gefunden", code="category_not_found")
    if category.kind not in kinds:
        raise DomainValidationError("Diese Kategorie passt nicht zur Buchungsart.")
    if category.archived:
        raise DomainValidationError("Diese Kategorie ist archiviert.")
    return category


def _local_day_start(day: date) -> datetime:
    return clock.as_utc(datetime.combine(day, time.min))


# ---------------------------------------------------------------- listing


def list_transactions(
    db: Session,
    *,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    bucket: Bucket | None = None,
    type_: TransactionType | None = None,
    min_amount: int | None = None,
    max_amount: int | None = None,
    period_id: int | None = None,
    is_recurring: bool | None = None,
    sort: SortField = "occurred_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> TransactionListOut:
    stmt = select(Transaction)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.outerjoin(Category, Transaction.category_id == Category.id).where(
            or_(
                Transaction.description.ilike(pattern),
                Transaction.merchant.ilike(pattern),
                Category.name.ilike(pattern),
            )
        )
    if date_from:
        stmt = stmt.where(Transaction.occurred_at >= _local_day_start(date_from))
    if date_to:
        stmt = stmt.where(Transaction.occurred_at < _local_day_start(date_to + timedelta(days=1)))
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if bucket is not None:
        stmt = stmt.where(Transaction.bucket == bucket)
    if type_ is not None:
        stmt = stmt.where(Transaction.type == type_)
    if min_amount is not None:
        stmt = stmt.where(Transaction.amount_cents >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(Transaction.amount_cents <= max_amount)
    if period_id is not None:
        stmt = stmt.where(Transaction.period_id == period_id)
    if is_recurring is not None:
        recurring = (Transaction.is_recurring.is_(True)) | (Transaction.recurring_expense_id.is_not(None))
        stmt = stmt.where(recurring if is_recurring else ~recurring)

    filtered = stmt.subquery()
    total, expense_sum, income_sum = db.execute(
        select(
            func.count(),
            func.coalesce(
                func.sum(filtered.c.amount_cents).filter(filtered.c.type == TransactionType.EXPENSE.value),
                0,
            ),
            func.coalesce(
                func.sum(filtered.c.amount_cents).filter(
                    filtered.c.type == TransactionType.INCOME.value,
                    filtered.c.reversed_at.is_(None),
                ),
                0,
            ),
        ).select_from(filtered)
    ).one()
    direction = desc if order == "desc" else asc
    column = getattr(Transaction, sort)
    items = db.scalars(
        stmt.order_by(direction(column), direction(Transaction.id)).limit(limit).offset(offset)
    ).unique()
    return TransactionListOut(
        items=[to_out(t) for t in items],
        total=total,
        expense_sum_cents=expense_sum,
        income_sum_cents=income_sum,
    )


# ---------------------------------------------------------------- expenses


def create_expense(db: Session, data: ExpenseIn) -> TransactionOut:
    if data.recurring_expense_id is not None:
        recurring = db.get(RecurringExpense, data.recurring_expense_id)
        if recurring is None:
            raise DomainValidationError("Fixkosten-Eintrag nicht gefunden")
    category = _category(db, data.category_id, {CategoryKind.FIXED, CategoryKind.LEISURE})
    period = require_period_at(db, data.occurred_at)
    before = snapshot_closed(db, [period.id])
    txn = Transaction(
        type=TransactionType.EXPENSE,
        occurred_at=data.occurred_at,
        amount_cents=data.amount_cents,
        bucket=Bucket(category.kind.value),
        category_id=category.id,
        description=data.description,
        merchant=data.merchant,
        period_id=period.id,
        recurring_expense_id=data.recurring_expense_id,
        is_recurring=data.is_recurring or data.recurring_expense_id is not None,
    )
    db.add(txn)
    db.flush()
    settle_closed_periods(
        db,
        before,
        action=CorrectionAction.CREATE,
        transaction_id=txn.id,
        confirm=data.confirm_correction,
        reason=data.correction_reason
        or f"Nachgetragene Ausgabe „{txn.description}“ ({format_eur(txn.amount_cents)})",
    )
    db.refresh(txn)
    return to_out(txn)


def update_transaction(db: Session, txn_id: int, data: TransactionUpdate) -> TransactionOut:
    txn = get_transaction(db, txn_id)
    if txn.reversed_at is not None:
        raise ConflictError("Stornierte Buchungen können nicht mehr bearbeitet werden.")
    fields = data.model_dump(exclude_unset=True, exclude={"confirm_correction", "correction_reason"})
    if txn.type != TransactionType.EXPENSE:
        money_fields = {"occurred_at", "amount_cents"} & {
            k for k, v in fields.items() if v != getattr(txn, k)
        }
        if money_fields:
            hint = (
                "Korrigiere den Gehaltsbetrag über „Gehalt korrigieren“."
                if txn.income_kind == IncomeKind.SALARY
                else "Storniere die Buchung und erfasse sie neu."
            )
            raise DomainValidationError(
                f"Betrag und Datum von Einnahmen und Umbuchungen sind fest. {hint}",
                code="immutable_money_fields",
            )
        if "category_id" in fields and fields["category_id"] is not None:
            _category(db, fields["category_id"], {CategoryKind.INCOME})
        for key in ("description", "merchant", "category_id", "is_recurring"):
            if key in fields:
                setattr(txn, key, fields[key])
        db.flush()
        db.refresh(txn)
        return to_out(txn)

    new_period_id = (
        require_period_at(db, fields["occurred_at"]).id
        if fields.get("occurred_at") is not None
        else txn.period_id
    )
    before = snapshot_closed(db, [txn.period_id, new_period_id])
    if "category_id" in fields and fields["category_id"] is not None:
        category = _category(db, fields["category_id"], {CategoryKind.FIXED, CategoryKind.LEISURE})
        txn.category_id = category.id
        txn.bucket = Bucket(category.kind.value)
    if fields.get("occurred_at") is not None:
        txn.occurred_at = fields["occurred_at"]
        txn.period_id = new_period_id
    if fields.get("amount_cents") is not None:
        txn.amount_cents = fields["amount_cents"]
    for key in ("description", "merchant", "is_recurring"):
        if key in fields and (fields[key] is not None or key == "merchant"):
            setattr(txn, key, fields[key])
    db.flush()
    settle_closed_periods(
        db,
        before,
        action=CorrectionAction.UPDATE,
        transaction_id=txn.id,
        confirm=data.confirm_correction,
        reason=data.correction_reason
        or f"Ausgabe „{txn.description}“ nachträglich geändert ({format_eur(txn.amount_cents)})",
    )
    db.refresh(txn)
    return to_out(txn)


def delete_transaction(db: Session, txn_id: int, *, confirm: bool, reason: str | None) -> None:
    txn = get_transaction(db, txn_id)
    if txn.type != TransactionType.EXPENSE:
        raise DomainValidationError(
            "Einnahmen und Umbuchungen werden storniert statt gelöscht, damit Reserve und "
            "Sparen nachvollziehbar bleiben.",
            code="use_reversal",
        )
    before = snapshot_closed(db, [txn.period_id])
    label = f"Ausgabe „{txn.description}“ ({format_eur(txn.amount_cents)}) gelöscht"
    db.delete(txn)
    db.flush()
    settle_closed_periods(
        db,
        before,
        action=CorrectionAction.DELETE,
        transaction_id=None,
        confirm=confirm,
        reason=reason or label,
    )


# ---------------------------------------------------------------- incomes


def create_income(db: Session, data: IncomeIn) -> TransactionOut:
    category: Category | None
    if data.category_id is not None:
        category = _category(db, data.category_id, {CategoryKind.INCOME})
    else:
        category = db.scalar(
            select(Category).where(
                Category.kind == CategoryKind.INCOME, Category.name == "Sonstige Einnahmen"
            )
        )
    if category is not None and category.name == "Gehalt":
        raise DomainValidationError(
            "Gehälter werden über „Gehalt erfassen“ gebucht, weil sie eine neue Budgetperiode eröffnen.",
            code="salary_via_salary_flow",
        )
    period = (
        require_period_at(db, data.occurred_at)
        if data.target == Pot.PERIOD
        else period_at(db, data.occurred_at)
    )
    before = snapshot_closed(db, [period.id] if period and data.target == Pot.PERIOD else [])
    txn = Transaction(
        type=TransactionType.INCOME,
        occurred_at=data.occurred_at,
        amount_cents=data.amount_cents,
        category_id=category.id if category else None,
        description=data.description,
        period_id=period.id if period else None,
        income_kind=IncomeKind.OTHER,
        income_target=data.target,
        bucket=data.bucket if data.target == Pot.PERIOD else None,
    )
    db.add(txn)
    db.flush()
    match data.target:
        case Pot.PERIOD:
            assert period is not None
            db.add(
                BudgetAllocation(
                    period_id=period.id,
                    bucket=data.bucket,
                    amount_cents=data.amount_cents,
                    source=AllocationSource.INCOME,
                    transaction_id=txn.id,
                    note=data.description,
                )
            )
        case Pot.RESERVE:
            ledgers.book_reserve(
                db,
                data.amount_cents,
                ReserveKind.INCOME,
                data.occurred_at,
                transaction_id=txn.id,
                note=data.description,
            )
        case Pot.SAVINGS:
            ledgers.book_savings(
                db,
                data.amount_cents,
                SavingsKind.INCOME,
                data.occurred_at,
                transaction_id=txn.id,
                note=data.description,
            )
    db.flush()
    if data.target == Pot.PERIOD:
        settle_closed_periods(
            db,
            before,
            action=CorrectionAction.CREATE,
            transaction_id=txn.id,
            confirm=data.confirm_correction,
            reason=data.correction_reason
            or f"Nachgetragene Einnahme „{txn.description}“ ({format_eur(txn.amount_cents)})",
        )
    db.refresh(txn)
    return to_out(txn)


# ---------------------------------------------------------------- transfers


def _release_from_goal(db: Session, goal_id: int, amount: int, note: str) -> None:
    goal = db.get(SavingsGoal, goal_id)
    if goal is None:
        raise NotFoundError("Sparziel nicht gefunden")
    saved = (
        db.scalar(
            select(func.coalesce(func.sum(SavingsAllocation.amount_cents), 0)).where(
                SavingsAllocation.goal_id == goal_id
            )
        )
        or 0
    )
    if saved < amount:
        raise DomainValidationError(f"Im Sparziel „{goal.title}“ sind nur {format_eur(saved)} angespart.")
    db.add(SavingsAllocation(goal_id=goal_id, amount_cents=-amount, note=note))
    db.flush()


def create_transfer(db: Session, data: TransferIn) -> TransactionOut:
    now = clock.now()
    period = require_active_period(db) if Pot.PERIOD in (data.from_pot, data.to_pot) else None
    label = f"Umbuchung {_pot_label(data.from_pot, data.bucket)} → {_pot_label(data.to_pot, data.bucket)}"

    if data.from_pot == Pot.RESERVE and ledgers.reserve_balance(db) < data.amount_cents:
        raise DomainValidationError("Die Reserve reicht dafür nicht aus.", code="reserve_insufficient")
    if data.from_pot == Pot.SAVINGS:
        if data.savings_goal_id is not None:
            _release_from_goal(db, data.savings_goal_id, data.amount_cents, label)
        if ledgers.savings_unallocated(db) < data.amount_cents:
            raise DomainValidationError(
                "Nicht genug freies Erspartes. Gib zuerst Geld aus einem Sparziel frei.",
                code="savings_insufficient",
            )
    if data.from_pot == Pot.PERIOD:
        assert period is not None and data.bucket is not None
        available = bucket_statuses(db, period.id)[data.bucket].available
        if available < data.amount_cents:
            raise DomainValidationError(
                f"Im Topf {BUCKET_LABELS[data.bucket]} sind nur {format_eur(available)} verfügbar."
            )

    txn = Transaction(
        type=TransactionType.TRANSFER,
        occurred_at=now,
        amount_cents=data.amount_cents,
        bucket=data.bucket if period else None,
        description=data.note or label,
        period_id=period.id if period else (p.id if (p := active_period(db)) else None),
        transfer_from=data.from_pot,
        transfer_to=data.to_pot,
    )
    db.add(txn)
    db.flush()
    for pot, sign in ((data.from_pot, -1), (data.to_pot, 1)):
        amount = sign * data.amount_cents
        match pot:
            case Pot.RESERVE:
                ledgers.book_reserve(
                    db, amount, ReserveKind.TRANSFER, now, transaction_id=txn.id, note=txn.description
                )
            case Pot.SAVINGS:
                ledgers.book_savings(
                    db, amount, SavingsKind.TRANSFER, now, transaction_id=txn.id, note=txn.description
                )
            case Pot.PERIOD:
                assert period is not None and data.bucket is not None
                db.add(
                    BudgetAllocation(
                        period_id=period.id,
                        bucket=data.bucket,
                        amount_cents=amount,
                        source=AllocationSource.TRANSFER,
                        transaction_id=txn.id,
                        note=txn.description,
                    )
                )
    db.flush()
    db.refresh(txn)
    return to_out(txn)


def _pot_label(pot: Pot, bucket: Bucket | None) -> str:
    if pot == Pot.PERIOD and bucket is not None:
        return f"Budget ({BUCKET_LABELS[bucket]})"
    return POT_LABELS[pot]


# ---------------------------------------------------------------- reversal


def reverse_transaction(db: Session, txn_id: int, *, confirm: bool, reason: str | None) -> TransactionOut:
    txn = get_transaction(db, txn_id)
    if txn.type == TransactionType.EXPENSE:
        raise DomainValidationError("Ausgaben werden bearbeitet oder gelöscht, nicht storniert.")
    if txn.income_kind == IncomeKind.SALARY:
        raise DomainValidationError(
            "Ein Gehalt eröffnet einen Budgetzeitraum und kann nicht storniert werden. "
            "Korrigiere den Betrag über „Gehalt korrigieren“.",
            code="salary_not_reversible",
        )
    if txn.reversed_at is not None:
        raise ConflictError("Diese Buchung wurde bereits storniert.", code="already_reversed")

    now = clock.now()
    note = reason or f"Storno: {txn.description}"
    allocations = db.scalars(select(BudgetAllocation).where(BudgetAllocation.transaction_id == txn.id)).all()
    reserve_rows = db.scalars(
        select(ReserveEntry).where(
            ReserveEntry.transaction_id == txn.id,
            ReserveEntry.kind != ReserveKind.PERIOD_CORRECTION,
        )
    ).all()
    savings_rows = db.scalars(select(SavingsEntry).where(SavingsEntry.transaction_id == txn.id)).all()

    before = snapshot_closed(db, [a.period_id for a in allocations])
    reserve_delta = -sum(r.amount_cents for r in reserve_rows)
    if reserve_delta < 0 and ledgers.reserve_balance(db) + reserve_delta < 0:
        raise DomainValidationError(
            "Die Reserve reicht für dieses Storno nicht aus.", code="reserve_insufficient"
        )
    savings_delta = -sum(s.amount_cents for s in savings_rows)
    if savings_delta < 0 and ledgers.savings_unallocated(db) + savings_delta < 0:
        raise DomainValidationError(
            "Nicht genug freies Erspartes für dieses Storno. Gib zuerst Geld aus einem Sparziel frei.",
            code="savings_insufficient",
        )

    for a in allocations:
        db.add(
            BudgetAllocation(
                period_id=a.period_id,
                bucket=a.bucket,
                amount_cents=-a.amount_cents,
                source=AllocationSource.REVERSAL
                if a.source == AllocationSource.INCOME
                else AllocationSource.TRANSFER,
                transaction_id=txn.id,
                note=note[:255],
            )
        )
    for r in reserve_rows:
        ledgers.book_reserve(
            db,
            -r.amount_cents,
            ReserveKind.REVERSAL,
            now,
            period_id=r.period_id,
            transaction_id=txn.id,
            note=note,
        )
    for s in savings_rows:
        ledgers.book_savings(
            db,
            -s.amount_cents,
            SavingsKind.REVERSAL,
            now,
            period_id=s.period_id,
            transaction_id=txn.id,
            note=note,
        )
    txn.reversed_at = now
    db.flush()
    settle_closed_periods(
        db,
        before,
        action=CorrectionAction.REVERSAL,
        transaction_id=txn.id,
        confirm=confirm,
        reason=note,
    )
    db.refresh(txn)
    return to_out(txn)


# ------------------------------------------------------- recurring detection


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def recurring_suggestions(db: Session) -> list[RecurringSuggestionOut]:
    """Expenses with the same payee or text and a similar amount in at least two
    different periods, not yet linked to a planned fixed cost."""
    expenses = db.scalars(
        select(Transaction).where(
            Transaction.type == TransactionType.EXPENSE,
            Transaction.recurring_expense_id.is_(None),
            Transaction.is_recurring.is_(False),
        )
    ).unique()
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in expenses:
        groups[_normalize(t.merchant or t.description)].append(t)
    suggestions: list[RecurringSuggestionOut] = []
    for items in groups.values():
        periods = {t.period_id for t in items}
        if len(periods) < 2:
            continue
        median = int(statistics.median(t.amount_cents for t in items))
        similar = [t for t in items if abs(t.amount_cents - median) * 10 <= median]
        if len({t.period_id for t in similar}) < 2:
            continue
        latest = max(similar, key=lambda t: t.occurred_at)
        suggestions.append(
            RecurringSuggestionOut(
                label=latest.merchant or latest.description,
                merchant=latest.merchant,
                category=CategoryRef.model_validate(latest.category) if latest.category else None,
                typical_amount_cents=median,
                occurrences=len(similar),
                periods=len({t.period_id for t in similar}),
                transaction_ids=sorted(t.id for t in similar),
            )
        )
    return sorted(suggestions, key=lambda s: -s.occurrences)


def mark_recurring(db: Session, ids: list[int], value: bool) -> int:
    rows = db.scalars(select(Transaction).where(Transaction.id.in_(ids))).unique().all()
    for t in rows:
        t.is_recurring = value
    db.flush()
    return len(rows)
