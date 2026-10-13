"""Close-out math of a budget period. Pure: numbers in, numbers out."""

from dataclasses import dataclass

from app.domain.budget_models import SPENDING_BUCKETS, Bucket
from app.domain.money import Cents, basis_points


@dataclass(frozen=True)
class BucketStatus:
    bucket: Bucket
    budget: Cents
    spent: Cents

    @property
    def available(self) -> Cents:
        return self.budget - self.spent

    @property
    def used_bp(self) -> int | None:
        return basis_points(self.spent, self.budget)


@dataclass(frozen=True)
class ClosingResult:
    """Unspent fixed and leisure budget are netted against each other.

    A positive sum goes to the reserve. A negative sum is a deficit and never
    produces a reserve credit. The savings bucket is not part of this math.
    """

    leftover: Cents

    @property
    def reserve_transfer(self) -> Cents:
        return max(self.leftover, 0)

    @property
    def deficit(self) -> Cents:
        return max(-self.leftover, 0)


def compute_closing(buckets: dict[Bucket, BucketStatus]) -> ClosingResult:
    return ClosingResult(leftover=sum(buckets[b].available for b in SPENDING_BUCKETS))
