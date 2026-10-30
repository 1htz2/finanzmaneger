"""Budget warnings as a registry of small rules over one snapshot."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.domain.closing import BucketStatus
from app.domain.money import Cents, format_eur
from app.domain.pacing import LeisurePace


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BudgetWarning:
    code: str
    severity: Severity
    title: str
    message: str


@dataclass(frozen=True)
class LargeExpense:
    description: str
    amount: Cents


@dataclass(frozen=True)
class WarningContext:
    leisure: BucketStatus
    fixed: BucketStatus
    fixed_open_planned: Cents
    reserve_balance: Cents
    reserve_minimum: Cents
    large_expenses: list[LargeExpense]
    pace: LeisurePace | None


def _leisure_usage(ctx: WarningContext) -> list[BudgetWarning]:
    s = ctx.leisure
    if s.budget <= 0 and s.spent <= 0:
        return []
    if s.spent > s.budget:
        return [
            BudgetWarning(
                "leisure_exceeded",
                Severity.CRITICAL,
                "Freizeitbudget überschritten",
                f"Du hast {format_eur(s.spent - s.budget)} mehr ausgegeben als geplant.",
            )
        ]
    used = s.used_bp or 0
    for threshold, severity in ((9000, Severity.WARNING), (7500, Severity.INFO)):
        if used >= threshold:
            return [
                BudgetWarning(
                    f"leisure_{threshold // 100}",
                    severity,
                    f"{threshold // 100} % des Freizeitbudgets verbraucht",
                    f"Noch {format_eur(s.available)} verfügbar.",
                )
            ]
    return []


def _fixed_sufficiency(ctx: WarningContext) -> list[BudgetWarning]:
    needed = ctx.fixed.spent + ctx.fixed_open_planned
    if needed <= ctx.fixed.budget:
        return []
    return [
        BudgetWarning(
            "fixed_insufficient",
            Severity.WARNING,
            "Fixkostenbudget zu klein",
            f"Gebuchte und noch offene Fixkosten liegen {format_eur(needed - ctx.fixed.budget)} "
            "über dem Fixkostenbudget.",
        )
    ]


def _large_expenses(ctx: WarningContext) -> list[BudgetWarning]:
    return [
        BudgetWarning(
            "large_expense",
            Severity.INFO,
            "Große Ausgabe",
            f"{e.description}: {format_eur(e.amount)}",
        )
        for e in ctx.large_expenses
    ]


def _reserve_minimum(ctx: WarningContext) -> list[BudgetWarning]:
    if ctx.reserve_balance < 0:
        return [
            BudgetWarning(
                "reserve_negative",
                Severity.CRITICAL,
                "Reserve im Minus",
                f"Nachträgliche Korrekturen haben mehr verbraucht, als in der Reserve lag: "
                f"{format_eur(ctx.reserve_balance)}.",
            )
        ]
    if ctx.reserve_minimum <= 0 or ctx.reserve_balance >= ctx.reserve_minimum:
        return []
    return [
        BudgetWarning(
            "reserve_low",
            Severity.INFO,
            "Notfallreserve noch unter Ziel",
            f"{format_eur(ctx.reserve_balance)} von {format_eur(ctx.reserve_minimum)}, "
            f"es fehlen {format_eur(ctx.reserve_minimum - ctx.reserve_balance)}.",
        )
    ]


def _pace(ctx: WarningContext) -> list[BudgetWarning]:
    pace = ctx.pace
    if pace is None or pace.ahead_of_plan_by <= 0 or ctx.leisure.spent > ctx.leisure.budget:
        return []
    return [
        BudgetWarning(
            "leisure_pace",
            Severity.INFO,
            "Über dem geplanten Tagesdurchschnitt",
            f"Bis heute {format_eur(pace.ahead_of_plan_by)} mehr Freizeitausgaben als bei "
            "gleichmäßiger Verteilung.",
        )
    ]


RULES: tuple[Callable[[WarningContext], list[BudgetWarning]], ...] = (
    _leisure_usage,
    _fixed_sufficiency,
    _reserve_minimum,
    _pace,
    _large_expenses,
)

_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


def evaluate_warnings(ctx: WarningContext) -> list[BudgetWarning]:
    found = [w for rule in RULES for w in rule(ctx)]
    return sorted(found, key=lambda w: _SEVERITY_ORDER[w.severity])
