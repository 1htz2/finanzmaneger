"""Schedules of planned fixed costs. Planned costs are never actual spending."""

import calendar
from datetime import date
from enum import StrEnum

from app.domain.money import Cents, divide_half_up


class Interval(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


INTERVAL_MONTHS: dict[Interval, int] = {
    Interval.MONTHLY: 1,
    Interval.QUARTERLY: 3,
    Interval.YEARLY: 12,
}


def monthly_equivalent(amount: Cents, interval: Interval) -> Cents:
    """120 € per year -> 10 € per month (rounded half up to the cent)."""
    return divide_half_up(amount, INTERVAL_MONTHS[interval])


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def occurrences(anchor: date, interval: Interval, start: date, end: date) -> list[date]:
    """Due dates in ``[start, end)`` for a cost due on ``anchor`` every interval.

    Stepping is always computed from the anchor so day clamping (31st -> 28th)
    does not drift over the months.
    """
    step = INTERVAL_MONTHS[interval]
    months_between = (start.year - anchor.year) * 12 + (start.month - anchor.month)
    k = (months_between // step) - 1
    result: list[date] = []
    while True:
        due = add_months(anchor, k * step)
        if due >= end:
            return result
        if due >= start:
            result.append(due)
        k += 1
