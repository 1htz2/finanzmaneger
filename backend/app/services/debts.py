"""Debts the user owes. Repayments are ordinary expenses linked by ``debt_id``,
so they count against the budget exactly once and lower the remaining amount."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.domain.enums import CategoryKind, TransactionType
from app.domain.money import basis_points, format_eur
from app.domain.recurring import Interval, add_months
from app.models import Category, Debt, RecurringExpense, Transaction
from app.schemas.debts import DebtIn, DebtOut, DebtsOverviewOut, DebtUpdate
from app.services.periods import active_period

RATE_CATEGORY = "Kredite und Raten"

Repaid = tuple[int, int, datetime | None]


def _get(db: Session, debt_id: int) -> Debt:
    debt = db.get(Debt, debt_id)
    if debt is None:
        raise NotFoundError("Schuld nicht gefunden")
    return debt


def _repayments(db: Session) -> dict[int, Repaid]:
    rows = db.execute(
        select(
            Transaction.debt_id,
            func.sum(Transaction.amount_cents),
            func.count(),
            func.max(Transaction.occurred_at),
        )
        .where(Transaction.debt_id.is_not(None), Transaction.type == TransactionType.EXPENSE)
        .group_by(Transaction.debt_id)
    ).all()
    return {debt_id: (total, count, last) for debt_id, total, count, last in rows if debt_id is not None}


def repaid(db: Session, debt_id: int, *, exclude_txn_id: int | None = None) -> int:
    stmt = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.debt_id == debt_id, Transaction.type == TransactionType.EXPENSE
    )
    if exclude_txn_id is not None:
        stmt = stmt.where(Transaction.id != exclude_txn_id)
    return db.scalar(stmt) or 0


def check_repayment(
    db: Session, debt_id: int, amount: int, *, exclude_txn_id: int | None = None, new: bool = False
) -> None:
    """A repayment must not exceed what is still owed."""
    debt = _get(db, debt_id)
    if new and debt.archived:
        raise DomainValidationError("Diese Schuld ist archiviert.")
    remaining = debt.opening_balance_cents - repaid(db, debt_id, exclude_txn_id=exclude_txn_id)
    if amount > remaining:
        raise DomainValidationError(
            f"„{debt.name}“ hat nur noch {format_eur(remaining)} Restschuld.", code="debt_overpaid"
        )


def _out(debt: Debt, paid: Repaid | None, planned: list[int]) -> DebtOut:
    repaid_cents, count, last = paid or (0, 0, None)
    remaining = debt.opening_balance_cents - repaid_cents
    projected = None
    if remaining > 0 and debt.monthly_rate_cents:
        months = -(-remaining // debt.monthly_rate_cents)
        projected = add_months(clock.today(), months)
    return DebtOut(
        id=debt.id,
        name=debt.name,
        creditor=debt.creditor,
        original_cents=debt.original_cents,
        opening_balance_cents=debt.opening_balance_cents,
        monthly_rate_cents=debt.monthly_rate_cents,
        note=debt.note,
        archived=debt.archived,
        status="paid_off" if remaining <= 0 else "open",
        repaid_cents=repaid_cents,
        remaining_cents=remaining,
        progress_bp=basis_points(debt.original_cents - remaining, debt.original_cents) or 0,
        repayment_count=count,
        last_repayment_at=last,
        projected_payoff=projected,
        planned_recurring_ids=planned,
        created_at=debt.created_at,
        updated_at=debt.updated_at,
    )


def _planned(db: Session) -> dict[int, list[int]]:
    planned: dict[int, list[int]] = {}
    for rid, debt_id in db.execute(
        select(RecurringExpense.id, RecurringExpense.debt_id)
        .where(RecurringExpense.debt_id.is_not(None))
        .order_by(RecurringExpense.id)
    ):
        if debt_id is not None:
            planned.setdefault(debt_id, []).append(rid)
    return planned


def get_debt(db: Session, debt_id: int) -> DebtOut:
    debt = _get(db, debt_id)
    return _out(debt, _repayments(db).get(debt.id), _planned(db).get(debt.id, []))


def overview(db: Session) -> DebtsOverviewOut:
    debts = list(db.scalars(select(Debt).order_by(Debt.archived, Debt.created_at, Debt.id)))
    paid = _repayments(db)
    planned = _planned(db)
    items = [_out(d, paid.get(d.id), planned.get(d.id, [])) for d in debts]
    open_items = [i for i in items if not i.archived and i.status == "open"]

    period = active_period(db)
    this_period = 0
    if period is not None:
        this_period = (
            db.scalar(
                select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
                    Transaction.debt_id.is_not(None), Transaction.period_id == period.id
                )
            )
            or 0
        )
    return DebtsOverviewOut(
        items=items,
        total_remaining_cents=sum(i.remaining_cents for i in open_items),
        total_original_cents=sum(i.original_cents for i in open_items),
        total_monthly_rate_cents=sum(i.monthly_rate_cents or 0 for i in open_items),
        repaid_this_period_cents=this_period,
    )


def _rate_category(db: Session, category_id: int | None) -> Category:
    if category_id is not None:
        category = db.get(Category, category_id)
    else:
        category = db.scalar(
            select(Category).where(Category.kind == CategoryKind.FIXED, Category.name == RATE_CATEGORY)
        )
    if category is None or category.kind != CategoryKind.FIXED or category.archived:
        raise DomainValidationError("Bitte eine aktive Fixkosten-Kategorie für die Rate wählen.")
    return category


def create_debt(db: Session, data: DebtIn) -> DebtOut:
    debt = Debt(
        name=data.name,
        creditor=data.creditor,
        original_cents=data.original_cents,
        opening_balance_cents=(
            data.original_cents if data.opening_balance_cents is None else data.opening_balance_cents
        ),
        monthly_rate_cents=data.monthly_rate_cents,
        note=data.note,
    )
    db.add(debt)
    db.flush()
    if data.plan_rate:
        assert data.monthly_rate_cents is not None
        db.add(
            RecurringExpense(
                name=f"Rate {data.name}",
                amount_cents=data.monthly_rate_cents,
                category_id=_rate_category(db, data.rate_category_id).id,
                interval=Interval.MONTHLY,
                due_date=data.rate_due_date,
                debt_id=debt.id,
            )
        )
        db.flush()
    return get_debt(db, debt.id)


def update_debt(db: Session, debt_id: int, data: DebtUpdate) -> DebtOut:
    debt = _get(db, debt_id)
    fields = data.model_dump(exclude_unset=True)
    for key in ("creditor", "note", "monthly_rate_cents"):
        if key in fields:
            setattr(debt, key, fields.pop(key))
    for key, value in fields.items():
        if value is not None:
            setattr(debt, key, value)
    if debt.opening_balance_cents > debt.original_cents:
        raise DomainValidationError("Die Restschuld kann nicht höher sein als der ursprüngliche Betrag.")
    already = repaid(db, debt.id)
    if debt.opening_balance_cents < already:
        raise DomainValidationError(
            f"Es sind bereits {format_eur(already)} zurückgezahlt. "
            "Die Restschuld bei Anlage kann nicht niedriger sein.",
            code="debt_overpaid",
        )
    db.flush()
    return get_debt(db, debt.id)


def delete_debt(db: Session, debt_id: int) -> None:
    """Only debts without repayments can be deleted; the others are archived so the
    history of the expenses stays understandable."""
    debt = _get(db, debt_id)
    if repaid(db, debt.id) > 0:
        raise ConflictError(
            "Für diese Schuld gibt es schon Rückzahlungen. Archiviere sie stattdessen.",
            code="debt_has_repayments",
        )
    for r in db.scalars(select(RecurringExpense).where(RecurringExpense.debt_id == debt.id)):
        r.debt_id = None
    db.delete(debt)
    db.flush()
