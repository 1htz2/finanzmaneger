"""Budget periods: lifecycle, salary-driven transitions and closed-period corrections.

The backend is the source of truth for every number shown in the UI.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import CorrectionRequiredError, DomainValidationError, NotFoundError
from app.domain.budget_models import SPENDING_BUCKETS, Bucket, get_budget_model
from app.domain.closing import BucketStatus, ClosingResult, compute_closing
from app.domain.enums import (
    AllocationSource,
    CategoryKind,
    CorrectionAction,
    IncomeKind,
    PeriodStatus,
    Pot,
    ReserveKind,
    SavingsKind,
    TransactionType,
)
from app.domain.money import basis_points, format_eur
from app.models import (
    BudgetAllocation,
    BudgetPeriod,
    Category,
    PeriodCorrection,
    Transaction,
)
from app.schemas.periods import (
    AllocationOut,
    BucketStatusOut,
    ClosingPreviewOut,
    CorrectionOut,
    PeriodDetailOut,
    PeriodSummaryOut,
    SalaryCorrectionIn,
    SalaryIn,
    SalaryPreviewIn,
    SalaryPreviewOut,
    SalaryResultOut,
    SplitOut,
)
from app.services import ledgers
from app.services.settings import get_app_settings

# ---------------------------------------------------------------- queries


def active_period(db: Session) -> BudgetPeriod | None:
    return db.scalar(select(BudgetPeriod).where(BudgetPeriod.status == PeriodStatus.ACTIVE))


def require_active_period(db: Session) -> BudgetPeriod:
    period = active_period(db)
    if period is None:
        raise DomainValidationError(
            "Es gibt noch keinen Budgetzeitraum. Erfasse zuerst einen Gehaltseingang.",
            code="no_active_period",
        )
    return period


def period_at(db: Session, at: datetime) -> BudgetPeriod | None:
    return db.scalar(
        select(BudgetPeriod).where(
            BudgetPeriod.started_at <= at,
            (BudgetPeriod.ended_at.is_(None)) | (BudgetPeriod.ended_at > at),
        )
    )


def require_period_at(db: Session, at: datetime) -> BudgetPeriod:
    period = period_at(db, at)
    if period is None:
        raise DomainValidationError(
            "Für dieses Datum gibt es keinen Budgetzeitraum. Buchungen sind erst ab dem "
            "ersten erfassten Gehaltseingang möglich.",
            code="no_period_for_date",
        )
    return period


def get_period(db: Session, period_id: int) -> BudgetPeriod:
    period = db.get(BudgetPeriod, period_id)
    if period is None:
        raise NotFoundError("Budgetzeitraum nicht gefunden")
    return period


def bucket_statuses(db: Session, period_id: int) -> dict[Bucket, BucketStatus]:
    budgets = dict(
        db.execute(
            select(BudgetAllocation.bucket, func.sum(BudgetAllocation.amount_cents))
            .where(BudgetAllocation.period_id == period_id)
            .group_by(BudgetAllocation.bucket)
        ).all()
    )
    spent = dict(
        db.execute(
            select(Transaction.bucket, func.sum(Transaction.amount_cents))
            .where(
                Transaction.period_id == period_id,
                Transaction.type == TransactionType.EXPENSE,
            )
            .group_by(Transaction.bucket)
        ).all()
    )
    return {b: BucketStatus(bucket=b, budget=budgets.get(b, 0), spent=spent.get(b, 0)) for b in Bucket}


def live_closing(db: Session, period_id: int) -> ClosingResult:
    return compute_closing(bucket_statuses(db, period_id))


def _allocation_sum(db: Session, period_id: int, source: AllocationSource) -> int:
    return (
        db.scalar(
            select(func.coalesce(func.sum(BudgetAllocation.amount_cents), 0)).where(
                BudgetAllocation.period_id == period_id, BudgetAllocation.source == source
            )
        )
        or 0
    )


def summarize(db: Session, period: BudgetPeriod) -> PeriodSummaryOut:
    statuses = bucket_statuses(db, period.id)
    closing = compute_closing(statuses)
    model = get_budget_model(period.budget_model_key)
    extra_income = _allocation_sum(db, period.id, AllocationSource.INCOME) + _allocation_sum(
        db, period.id, AllocationSource.REVERSAL
    )
    spent = sum(statuses[b].spent for b in SPENDING_BUCKETS)
    income_total = period.net_salary_cents + extra_income
    actual_rate = (
        basis_points(income_total - spent, income_total) if period.status == PeriodStatus.CLOSED else None
    )
    count = db.scalar(select(func.count()).where(Transaction.period_id == period.id)) or 0
    return PeriodSummaryOut(
        id=period.id,
        status=period.status,
        started_at=period.started_at,
        ended_at=period.ended_at,
        budget_model_key=period.budget_model_key,
        net_salary_cents=period.net_salary_cents,
        extra_income_cents=extra_income,
        transfer_net_cents=_allocation_sum(db, period.id, AllocationSource.TRANSFER),
        total_budget_cents=sum(s.budget for s in statuses.values()),
        expected_next_payday=period.expected_next_payday,
        buckets=[
            BucketStatusOut(
                bucket=s.bucket,
                budget_cents=s.budget,
                spent_cents=s.spent,
                available_cents=s.available,
                used_bp=s.used_bp,
            )
            for s in statuses.values()
        ],
        spent_cents=spent,
        leftover_cents=closing.leftover,
        reserve_transfer_cents=closing.reserve_transfer,
        deficit_cents=closing.deficit,
        planned_savings_rate_bp=model.shares_percent[Bucket.SAVINGS] * 100,
        actual_savings_rate_bp=actual_rate,
        transaction_count=count,
    )


def detail(db: Session, period: BudgetPeriod) -> PeriodDetailOut:
    corrections = db.scalars(
        select(PeriodCorrection).where(PeriodCorrection.period_id == period.id).order_by(PeriodCorrection.id)
    ).all()
    return PeriodDetailOut(
        **summarize(db, period).model_dump(),
        allocations=[AllocationOut.model_validate(a) for a in period.allocations],
        corrections=[CorrectionOut.model_validate(c) for c in corrections],
    )


def list_periods(db: Session) -> list[PeriodSummaryOut]:
    periods = db.scalars(select(BudgetPeriod).order_by(BudgetPeriod.started_at.desc())).all()
    return [summarize(db, p) for p in periods]


def period_label(period: BudgetPeriod) -> str:
    start = clock.local_date(period.started_at).strftime("%d.%m.%Y")
    if period.ended_at is None:
        return f"seit {start}"
    end = clock.local_date(period.ended_at - timedelta(seconds=1)).strftime("%d.%m.%Y")
    return f"{start} – {end}"


# ------------------------------------------------- closed-period corrections


@dataclass(frozen=True)
class PeriodImpact:
    period_id: int
    label: str
    leftover_before_cents: int
    leftover_after_cents: int
    reserve_delta_cents: int
    reserve_balance_after_cents: int
    buckets_changed: bool


ClosedSnapshot = dict[int, dict[Bucket, BucketStatus]]


def snapshot_closed(db: Session, period_ids: Iterable[int | None]) -> ClosedSnapshot:
    """Bucket state of the closed periods among ``period_ids``. Take it BEFORE a change."""
    snap: ClosedSnapshot = {}
    for period_id in {p for p in period_ids if p is not None}:
        if get_period(db, period_id).status == PeriodStatus.CLOSED:
            snap[period_id] = bucket_statuses(db, period_id)
    return snap


def settle_closed_periods(
    db: Session,
    before: ClosedSnapshot,
    *,
    action: CorrectionAction,
    transaction_id: int | None,
    confirm: bool,
    reason: str,
) -> list[PeriodImpact]:
    """Call after mutating data of the periods captured in ``before``.

    Any change to a closed period, even one that only moves money between its
    buckets, needs ``confirm``. Without it a ``CorrectionRequiredError`` carries
    the preview and the request's transaction is rolled back. With it, the
    reserve difference is booked as a correction row and an audit row is written.
    """
    db.flush()
    changed: list[tuple[BudgetPeriod, int, int, bool]] = []
    for period_id, statuses_before in sorted(before.items()):
        period = get_period(db, period_id)
        statuses_after = bucket_statuses(db, period_id)
        leftover_before = period.closing_leftover_cents
        assert leftover_before is not None
        leftover_after = compute_closing(statuses_after).leftover
        buckets_changed = statuses_after != statuses_before
        if buckets_changed or leftover_after != leftover_before:
            changed.append((period, leftover_before, leftover_after, buckets_changed))
    if not changed:
        return []

    balance = ledgers.reserve_balance(db)
    impacts: list[PeriodImpact] = []
    for period, leftover_before, leftover_after, buckets_changed in changed:
        delta = max(leftover_after, 0) - max(leftover_before, 0)
        balance += delta
        impacts.append(
            PeriodImpact(
                period_id=period.id,
                label=period_label(period),
                leftover_before_cents=leftover_before,
                leftover_after_cents=leftover_after,
                reserve_delta_cents=delta,
                reserve_balance_after_cents=balance,
                buckets_changed=buckets_changed,
            )
        )
    if not confirm:
        raise CorrectionRequiredError(
            "Diese Änderung betrifft einen abgeschlossenen Budgetzeitraum. Bitte bestätige die Korrektur.",
            details=[i.__dict__ for i in impacts],
        )
    now = clock.now()
    for (period, *_), impact in zip(changed, impacts, strict=True):
        ledgers.book_reserve(
            db,
            impact.reserve_delta_cents,
            ReserveKind.PERIOD_CORRECTION,
            now,
            period_id=period.id,
            transaction_id=transaction_id,
            note=reason,
        )
        db.add(
            PeriodCorrection(
                period_id=period.id,
                transaction_id=transaction_id,
                action=action,
                leftover_before_cents=impact.leftover_before_cents,
                leftover_after_cents=impact.leftover_after_cents,
                reserve_delta_cents=impact.reserve_delta_cents,
                reason=reason,
            )
        )
        period.closing_leftover_cents = impact.leftover_after_cents
    db.flush()
    return impacts


# ------------------------------------------------------- salary transition


def _salary_category_id(db: Session) -> int | None:
    return db.scalar(
        select(Category.id).where(Category.kind == CategoryKind.INCOME, Category.name == "Gehalt")
    )


def _validate_salary_time(active: BudgetPeriod | None, received_at: datetime) -> None:
    if clock.local_date(received_at) > clock.today():
        raise DomainValidationError(
            "Ein Gehaltseingang kann nicht in der Zukunft liegen.", code="salary_in_future"
        )
    if active is not None and received_at <= active.started_at:
        raise DomainValidationError(
            "Der Gehaltseingang muss nach dem Beginn des aktuellen Budgetzeitraums "
            f"({period_label(active)}) liegen. Wurde dieses Gehalt bereits erfasst?",
            code="salary_before_active_period",
        )


def _cover_deficit_from_reserve(db: Session, period: BudgetPeriod, at: datetime) -> int:
    """Deliberate reserve coverage: a visible transfer reserve -> overspent buckets."""
    statuses = bucket_statuses(db, period.id)
    deficit = compute_closing(statuses).deficit
    amount = min(deficit, max(ledgers.reserve_balance(db), 0))
    if amount <= 0:
        return 0
    txn = Transaction(
        type=TransactionType.TRANSFER,
        occurred_at=at,
        amount_cents=amount,
        description="Defizit aus Reserve gedeckt",
        period_id=period.id,
        transfer_from=Pot.RESERVE,
        transfer_to=Pot.PERIOD,
    )
    db.add(txn)
    db.flush()
    ledgers.book_reserve(
        db,
        -amount,
        ReserveKind.TRANSFER,
        at,
        period_id=period.id,
        transaction_id=txn.id,
        note=f"Deckung Defizit {period_label(period)}",
    )
    remaining = amount
    for bucket in (Bucket.LEISURE, Bucket.FIXED):
        share = min(remaining, max(-statuses[bucket].available, 0))
        if share > 0:
            db.add(
                BudgetAllocation(
                    period_id=period.id,
                    bucket=bucket,
                    amount_cents=share,
                    source=AllocationSource.TRANSFER,
                    transaction_id=txn.id,
                    note="Deckung aus Reserve",
                )
            )
            remaining -= share
    if remaining > 0:
        # Overspending was compensated across buckets; any rest lands in leisure.
        db.add(
            BudgetAllocation(
                period_id=period.id,
                bucket=Bucket.LEISURE,
                amount_cents=remaining,
                source=AllocationSource.TRANSFER,
                transaction_id=txn.id,
                note="Deckung aus Reserve",
            )
        )
    db.flush()
    return amount


@dataclass(frozen=True)
class _Transition:
    closed: BudgetPeriod | None
    closing: ClosingResult | None
    covered: int
    moved_transactions: int
    opened: BudgetPeriod


def _close_and_open(db: Session, data: SalaryIn) -> _Transition:
    active = active_period(db)
    _validate_salary_time(active, data.received_at)
    if data.expected_next_payday and data.expected_next_payday <= clock.local_date(data.received_at):
        raise DomainValidationError("Der erwartete nächste Zahltag muss nach dem Geldeingang liegen.")

    settings = get_app_settings(db)
    model = get_budget_model(settings.budget_model_key)
    now = clock.now()

    if active is not None:
        active.status = PeriodStatus.CLOSED
        active.ended_at = data.received_at
        active.closing_leftover_cents = 0
        active.closed_at = now
        db.flush()

    opened = BudgetPeriod(
        started_at=data.received_at,
        status=PeriodStatus.ACTIVE,
        budget_model_key=model.key,
        net_salary_cents=data.amount_cents,
        expected_next_payday=data.expected_next_payday,
    )
    db.add(opened)
    db.flush()

    closing: ClosingResult | None = None
    covered = 0
    moved = 0
    if active is not None:
        moved_ids = list(
            db.scalars(
                select(Transaction.id).where(
                    Transaction.period_id == active.id,
                    Transaction.occurred_at >= data.received_at,
                )
            )
        )
        moved = len(moved_ids)
        if moved_ids:
            db.execute(update(Transaction).where(Transaction.id.in_(moved_ids)).values(period_id=opened.id))
            db.execute(
                update(BudgetAllocation)
                .where(BudgetAllocation.transaction_id.in_(moved_ids))
                .values(period_id=opened.id)
            )
        if data.cover_deficit_from_reserve:
            covered = _cover_deficit_from_reserve(db, active, data.received_at - timedelta(seconds=1))
        closing = live_closing(db, active.id)
        active.closing_leftover_cents = closing.leftover
        ledgers.book_reserve(
            db,
            closing.reserve_transfer,
            ReserveKind.PERIOD_CLOSE,
            data.received_at,
            period_id=active.id,
            note=f"Übertrag aus {period_label(active)}",
        )

    salary = Transaction(
        type=TransactionType.INCOME,
        occurred_at=data.received_at,
        amount_cents=data.amount_cents,
        category_id=_salary_category_id(db),
        description=data.description or "Gehalt",
        period_id=opened.id,
        income_kind=IncomeKind.SALARY,
        income_target=Pot.PERIOD,
    )
    db.add(salary)
    db.flush()
    split = model.split(data.amount_cents)
    for bucket, amount in split.items():
        if amount:
            db.add(
                BudgetAllocation(
                    period_id=opened.id,
                    bucket=bucket,
                    amount_cents=amount,
                    source=AllocationSource.SALARY,
                    transaction_id=salary.id,
                )
            )
    ledgers.book_savings(
        db,
        split[Bucket.SAVINGS],
        SavingsKind.PERIOD_SAVINGS,
        data.received_at,
        period_id=opened.id,
        transaction_id=salary.id,
        note=f"{model.shares_percent[Bucket.SAVINGS]} % von {format_eur(data.amount_cents)}",
    )
    db.flush()
    db.refresh(opened)
    if active is not None:
        db.refresh(active)
    return _Transition(active, closing, covered, moved, opened)


def preview_salary(db: Session, data: SalaryPreviewIn) -> SalaryPreviewOut:
    """Runs the real transition inside a savepoint and rolls it back, so the
    preview cannot drift from what recording the salary will do."""
    reserve_before = ledgers.reserve_balance(db)
    savings_before = ledgers.savings_balance(db)
    model = get_budget_model(get_app_settings(db).budget_model_key)
    nested = db.begin_nested()
    try:
        t = _close_and_open(db, SalaryIn(**data.model_dump()))
        closing_preview = None
        if t.closed is not None and t.closing is not None:
            closing_preview = ClosingPreviewOut(
                period=summarize(db, t.closed),
                leftover_cents=t.closing.leftover,
                reserve_transfer_cents=t.closing.reserve_transfer,
                deficit_cents=t.closing.deficit,
                coverable_from_reserve_cents=min(t.closing.deficit, max(reserve_before, 0)),
                transactions_moving_to_new_period=t.moved_transactions,
            )
        result = SalaryPreviewOut(
            closing=closing_preview,
            new_split=[
                SplitOut(bucket=b, percent=model.shares_percent[b], amount_cents=a)
                for b, a in model.split(data.amount_cents).items()
            ],
            budget_model_label=model.label,
            reserve_balance_before_cents=reserve_before,
            reserve_balance_after_cents=ledgers.reserve_balance(db),
            savings_balance_before_cents=savings_before,
            savings_balance_after_cents=ledgers.savings_balance(db),
        )
    finally:
        nested.rollback()
    return result


def record_salary(db: Session, data: SalaryIn) -> SalaryResultOut:
    t = _close_and_open(db, data)
    return SalaryResultOut(
        closed_period=summarize(db, t.closed) if t.closed else None,
        reserve_transfer_cents=t.closing.reserve_transfer if t.closing else 0,
        deficit_cents=t.closing.deficit if t.closing else 0,
        deficit_covered_cents=t.covered,
        new_period=summarize(db, t.opened),
        reserve_balance_cents=ledgers.reserve_balance(db),
        savings_balance_cents=ledgers.savings_balance(db),
    )


def correct_active_salary(db: Session, data: SalaryCorrectionIn) -> PeriodSummaryOut:
    """Fixes a typo in the current salary. Books delta rows instead of rewriting history."""
    period = require_active_period(db)
    salary = db.scalar(
        select(Transaction).where(
            Transaction.period_id == period.id, Transaction.income_kind == IncomeKind.SALARY
        )
    )
    assert salary is not None
    model = get_budget_model(period.budget_model_key)
    old, new = model.split(period.net_salary_cents), model.split(data.amount_cents)
    savings_delta = new[Bucket.SAVINGS] - old[Bucket.SAVINGS]
    if savings_delta < 0 and ledgers.savings_unallocated(db) < -savings_delta:
        raise DomainValidationError(
            "Der Sparanteil ist bereits Sparzielen zugewiesen. Gib zuerst Geld aus einem Sparziel frei."
        )
    now = clock.now()
    change = f"{format_eur(period.net_salary_cents)} → {format_eur(data.amount_cents)}"
    note = f"Gehaltskorrektur {change}: {data.reason}"
    for bucket in Bucket:
        delta = new[bucket] - old[bucket]
        if delta:
            db.add(
                BudgetAllocation(
                    period_id=period.id,
                    bucket=bucket,
                    amount_cents=delta,
                    source=AllocationSource.SALARY_CORRECTION,
                    transaction_id=salary.id,
                    note=note[:255],
                )
            )
    ledgers.book_savings(
        db,
        savings_delta,
        SavingsKind.SALARY_CORRECTION,
        now,
        period_id=period.id,
        transaction_id=salary.id,
        note=note,
    )
    period.net_salary_cents = data.amount_cents
    salary.amount_cents = data.amount_cents
    db.flush()
    return summarize(db, period)


def set_expected_payday(db: Session, payday: date | None) -> PeriodSummaryOut:
    period = require_active_period(db)
    if payday is not None and payday <= clock.local_date(period.started_at):
        raise DomainValidationError("Der erwartete Zahltag muss nach dem Periodenbeginn liegen.")
    period.expected_next_payday = payday
    db.flush()
    return summarize(db, period)


def cover_closed_deficit(
    db: Session, period_id: int, amount: int | None, reason: str | None
) -> PeriodDetailOut:
    period = get_period(db, period_id)
    if period.status != PeriodStatus.CLOSED:
        raise DomainValidationError("Nur abgeschlossene Zeiträume können nachträglich gedeckt werden.")
    deficit = live_closing(db, period.id).deficit
    if deficit <= 0:
        raise DomainValidationError("Dieser Zeitraum hat kein Defizit.")
    amount = deficit if amount is None else amount
    if amount > deficit:
        raise DomainValidationError(f"Höchstens {format_eur(deficit)} können gedeckt werden.")
    if amount > ledgers.reserve_balance(db):
        raise DomainValidationError("Die Reserve reicht dafür nicht aus.", code="reserve_insufficient")
    before = snapshot_closed(db, [period.id])
    now = clock.now()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        occurred_at=period.ended_at - timedelta(seconds=1) if period.ended_at else now,
        amount_cents=amount,
        description="Defizit aus Reserve gedeckt",
        period_id=period.id,
        transfer_from=Pot.RESERVE,
        transfer_to=Pot.PERIOD,
    )
    db.add(txn)
    db.flush()
    ledgers.book_reserve(
        db,
        -amount,
        ReserveKind.TRANSFER,
        now,
        period_id=period.id,
        transaction_id=txn.id,
        note=reason or f"Nachträgliche Deckung {period_label(period)}",
    )
    db.add(
        BudgetAllocation(
            period_id=period.id,
            bucket=Bucket.LEISURE,
            amount_cents=amount,
            source=AllocationSource.TRANSFER,
            transaction_id=txn.id,
            note="Nachträgliche Deckung aus Reserve",
        )
    )
    settle_closed_periods(
        db,
        before,
        action=CorrectionAction.TRANSFER,
        transaction_id=txn.id,
        confirm=True,
        reason=reason or f"Defizit {format_eur(amount)} aus Reserve gedeckt",
    )
    db.refresh(period)
    return detail(db, period)
