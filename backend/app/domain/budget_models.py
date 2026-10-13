"""Budget models split a net salary into buckets.

New models are added to ``BUDGET_MODELS``; nothing else needs to change.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.money import Cents


class Bucket(StrEnum):
    SAVINGS = "savings"
    FIXED = "fixed"
    LEISURE = "leisure"


SPENDING_BUCKETS: tuple[Bucket, ...] = (Bucket.FIXED, Bucket.LEISURE)


@dataclass(frozen=True)
class BudgetModel:
    key: str
    label: str
    shares_percent: dict[Bucket, int]

    def __post_init__(self) -> None:
        if sum(self.shares_percent.values()) != 100:
            raise ValueError(f"Budgetmodell {self.key}: Anteile ergeben nicht 100 %")
        if set(self.shares_percent) != set(Bucket):
            raise ValueError(f"Budgetmodell {self.key}: jeder Topf braucht einen Anteil")

    def split(self, net_cents: Cents) -> dict[Bucket, Cents]:
        """Largest-remainder split: shares are floored, leftover cents go to the
        buckets with the largest fractional remainder, so the sum is exact."""
        if net_cents < 0:
            raise ValueError("Nettogehalt darf nicht negativ sein")
        raw = {b: divmod(net_cents * p, 100) for b, p in self.shares_percent.items()}
        result = {b: q for b, (q, _) in raw.items()}
        leftover = net_cents - sum(result.values())
        order = sorted(raw, key=lambda b: (-raw[b][1], list(Bucket).index(b)))
        for bucket in order[:leftover]:
            result[bucket] += 1
        return result


BUDGET_MODELS: dict[str, BudgetModel] = {
    m.key: m
    for m in (
        BudgetModel(
            key="20-50-30",
            label="20 % Sparen · 50 % Fixkosten · 30 % Freizeit",
            shares_percent={Bucket.SAVINGS: 20, Bucket.FIXED: 50, Bucket.LEISURE: 30},
        ),
    )
}

DEFAULT_BUDGET_MODEL = "20-50-30"


def get_budget_model(key: str) -> BudgetModel:
    return BUDGET_MODELS[key]
