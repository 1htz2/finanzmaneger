"""Daily and weekly leisure guidance. A planning aid only: it never changes a budget."""

from dataclasses import dataclass
from datetime import date

from app.domain.money import Cents


@dataclass(frozen=True)
class LeisurePace:
    days_left: int
    per_day: Cents
    per_week: Cents
    planned_spent_by_today: Cents
    ahead_of_plan_by: Cents  # > 0 means more spent than the even pace allows


def compute_leisure_pace(
    *,
    budget: Cents,
    spent: Cents,
    period_start: date,
    today: date,
    expected_payday: date,
) -> LeisurePace | None:
    """Without an expected payday there is no forecast, and the caller gets ``None``.

    ``days_left`` counts today up to the day before the expected payday.
    Amounts are floored so following the advice never overspends.
    """
    days_left = (expected_payday - today).days
    total_days = (expected_payday - period_start).days
    if days_left <= 0 or total_days <= 0:
        return None
    available = max(budget - spent, 0)
    elapsed_days = min(max((today - period_start).days + 1, 0), total_days)
    planned = budget * elapsed_days // total_days
    return LeisurePace(
        days_left=days_left,
        per_day=available // days_left,
        per_week=min(available, available * 7 // days_left),
        planned_spent_by_today=planned,
        ahead_of_plan_by=spent - planned,
    )
