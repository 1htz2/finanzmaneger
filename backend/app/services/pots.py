"""Reserve and savings pots, including savings goals."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import DomainValidationError, NotFoundError
from app.domain.enums import ReserveKind, SavingsKind
from app.domain.money import basis_points, format_eur
from app.models import ReserveEntry, SavingsAllocation, SavingsEntry, SavingsGoal
from app.schemas.pots import (
    BalancePoint,
    GoalAllocateIn,
    GoalIn,
    GoalOut,
    GoalUpdate,
    ReserveDepositIn,
    ReserveEntryOut,
    ReserveOut,
    ReserveWithdrawIn,
    SavingsEntryOut,
    SavingsOut,
    SavingsWithdrawIn,
)
from app.services import ledgers
from app.services.settings import get_app_settings


def _running_balance(rows: list[ReserveEntry] | list[SavingsEntry]) -> list[BalancePoint]:
    balance = 0
    points: list[BalancePoint] = []
    for row in rows:
        balance += row.amount_cents
        points.append(BalancePoint(at=row.occurred_at, balance_cents=balance))
    return points


def _reserve_rows(db: Session) -> list[ReserveEntry]:
    return list(db.scalars(select(ReserveEntry).order_by(ReserveEntry.occurred_at, ReserveEntry.id)))


def _savings_rows(db: Session) -> list[SavingsEntry]:
    return list(db.scalars(select(SavingsEntry).order_by(SavingsEntry.occurred_at, SavingsEntry.id)))


def reserve_history(db: Session) -> list[BalancePoint]:
    return _running_balance(_reserve_rows(db))


def savings_history(db: Session) -> list[BalancePoint]:
    return _running_balance(_savings_rows(db))


# ---------------------------------------------------------------- reserve


def reserve_overview(db: Session) -> ReserveOut:
    rows = _reserve_rows(db)
    settings = get_app_settings(db)
    from_periods = sum(
        r.amount_cents for r in rows if r.kind in (ReserveKind.PERIOD_CLOSE, ReserveKind.PERIOD_CORRECTION)
    )
    withdrawn = -sum(r.amount_cents for r in rows if r.kind == ReserveKind.WITHDRAWAL)
    return ReserveOut(
        balance_cents=sum(r.amount_cents for r in rows),
        minimum_cents=settings.reserve_minimum_cents,
        purposes=settings.reserve_purposes,
        entries=[ReserveEntryOut.model_validate(r) for r in reversed(rows)],
        history=_running_balance(rows),
        total_from_periods_cents=from_periods,
        total_withdrawn_cents=withdrawn,
    )


def reserve_deposit(db: Session, data: ReserveDepositIn) -> ReserveEntryOut:
    entry = ledgers.book_reserve(
        db, data.amount_cents, ReserveKind.DEPOSIT, data.occurred_at or clock.now(), note=data.note
    )
    db.flush()
    return ReserveEntryOut.model_validate(entry)


def reserve_withdraw(db: Session, data: ReserveWithdrawIn) -> ReserveEntryOut:
    balance = ledgers.reserve_balance(db)
    if data.amount_cents > balance:
        raise DomainValidationError(
            f"Die Reserve beträgt nur {format_eur(balance)}.", code="reserve_insufficient"
        )
    entry = ledgers.book_reserve(
        db,
        -data.amount_cents,
        ReserveKind.WITHDRAWAL,
        data.occurred_at or clock.now(),
        purpose=data.purpose,
        note=data.reason,
    )
    db.flush()
    return ReserveEntryOut.model_validate(entry)


# ---------------------------------------------------------------- savings


def _goal_saved(db: Session) -> dict[int, int]:
    return dict(
        db.execute(
            select(SavingsAllocation.goal_id, func.sum(SavingsAllocation.amount_cents)).group_by(
                SavingsAllocation.goal_id
            )
        ).all()
    )


def _project(db: Session, goal: SavingsGoal, saved: int) -> date | None:
    """Projection from the goal's own saving pace since its first allocation.

    No pace (no money yet, or everything today) means no projection, not a guess.
    """
    remaining = goal.target_cents - saved
    if remaining <= 0:
        return None
    first = db.scalar(
        select(func.min(SavingsAllocation.created_at)).where(SavingsAllocation.goal_id == goal.id)
    )
    if first is None or saved <= 0:
        return None
    days = (clock.today() - clock.local_date(first)).days
    if days < 1:
        return None
    return clock.today() + timedelta(days=-(-remaining * days // saved))


def _goal_out(db: Session, goal: SavingsGoal, saved: int) -> GoalOut:
    remaining = max(goal.target_cents - saved, 0)
    required = None
    if goal.target_date and remaining > 0:
        months = max(
            (goal.target_date.year - clock.today().year) * 12 + goal.target_date.month - clock.today().month,
            1,
        )
        required = -(-remaining // months)
    return GoalOut(
        id=goal.id,
        title=goal.title,
        target_cents=goal.target_cents,
        target_date=goal.target_date,
        archived=goal.archived,
        saved_cents=saved,
        remaining_cents=remaining,
        progress_bp=min(basis_points(saved, goal.target_cents) or 0, 10_000),
        projected_date=_project(db, goal, saved),
        required_per_month_cents=required,
        created_at=goal.created_at,
    )


def list_goals(db: Session, include_archived: bool = False) -> list[GoalOut]:
    stmt = select(SavingsGoal).order_by(SavingsGoal.archived, SavingsGoal.created_at)
    if not include_archived:
        stmt = stmt.where(SavingsGoal.archived.is_(False))
    saved = _goal_saved(db)
    return [_goal_out(db, g, saved.get(g.id, 0)) for g in db.scalars(stmt)]


def savings_overview(db: Session) -> SavingsOut:
    rows = _savings_rows(db)
    balance = sum(r.amount_cents for r in rows)
    allocated = ledgers.savings_allocated(db)
    return SavingsOut(
        balance_cents=balance,
        allocated_cents=allocated,
        unallocated_cents=balance - allocated,
        entries=[SavingsEntryOut.model_validate(r) for r in reversed(rows)],
        goals=list_goals(db, include_archived=True),
        history=_running_balance(rows),
    )


def _get_goal(db: Session, goal_id: int) -> SavingsGoal:
    goal = db.get(SavingsGoal, goal_id)
    if goal is None:
        raise NotFoundError("Sparziel nicht gefunden")
    return goal


def create_goal(db: Session, data: GoalIn) -> GoalOut:
    goal = SavingsGoal(**data.model_dump())
    db.add(goal)
    db.flush()
    return _goal_out(db, goal, 0)


def update_goal(db: Session, goal_id: int, data: GoalUpdate) -> GoalOut:
    goal = _get_goal(db, goal_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None or key == "target_date":
            setattr(goal, key, value)
    db.flush()
    return _goal_out(db, goal, _goal_saved(db).get(goal.id, 0))


def delete_goal(db: Session, goal_id: int) -> None:
    """Deleting releases the earmarked money back to free savings; nothing is lost."""
    goal = _get_goal(db, goal_id)
    for allocation in db.scalars(select(SavingsAllocation).where(SavingsAllocation.goal_id == goal.id)):
        db.delete(allocation)
    db.delete(goal)
    db.flush()


def allocate_to_goal(db: Session, goal_id: int, data: GoalAllocateIn) -> GoalOut:
    if data.amount_cents == 0:
        raise DomainValidationError("Der Betrag darf nicht 0 sein.")
    goal = _get_goal(db, goal_id)
    saved = _goal_saved(db).get(goal.id, 0)
    if data.amount_cents > 0:
        free = ledgers.savings_unallocated(db)
        if data.amount_cents > free:
            raise DomainValidationError(
                f"Es sind nur {format_eur(free)} freies Erspartes verfügbar.",
                code="savings_insufficient",
            )
    elif -data.amount_cents > saved:
        raise DomainValidationError(f"Im Sparziel sind nur {format_eur(saved)} angespart.")
    db.add(SavingsAllocation(goal_id=goal.id, amount_cents=data.amount_cents, note=data.note))
    db.flush()
    return _goal_out(db, goal, saved + data.amount_cents)


def savings_withdraw(db: Session, data: SavingsWithdrawIn) -> SavingsEntryOut:
    if data.goal_id is not None:
        goal = _get_goal(db, data.goal_id)
        saved = _goal_saved(db).get(goal.id, 0)
        if saved < data.amount_cents:
            raise DomainValidationError(f"Im Sparziel sind nur {format_eur(saved)} angespart.")
        db.add(SavingsAllocation(goal_id=goal.id, amount_cents=-data.amount_cents, note=data.reason))
        db.flush()
    free = ledgers.savings_unallocated(db)
    if data.amount_cents > free:
        raise DomainValidationError(
            f"Es sind nur {format_eur(free)} freies Erspartes verfügbar. "
            "Wähle das Sparziel, aus dem entnommen wird.",
            code="savings_insufficient",
        )
    entry = ledgers.book_savings(
        db, -data.amount_cents, SavingsKind.WITHDRAWAL, clock.now(), note=data.reason
    )
    db.flush()
    return SavingsEntryOut.model_validate(entry)
