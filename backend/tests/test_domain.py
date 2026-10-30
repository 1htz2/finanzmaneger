from datetime import date

import pytest

from app.domain.budget_models import Bucket, BudgetModel, get_budget_model
from app.domain.closing import BucketStatus, compute_closing
from app.domain.money import basis_points, format_eur
from app.domain.pacing import compute_leisure_pace
from app.domain.recurring import Interval, monthly_equivalent, occurrences
from app.domain.warnings import LargeExpense, WarningContext, evaluate_warnings

MODEL = get_budget_model("20-50-30")


def test_split_1300_euro() -> None:
    assert MODEL.split(130_000) == {Bucket.SAVINGS: 26_000, Bucket.FIXED: 65_000, Bucket.LEISURE: 39_000}


def test_split_1500_euro() -> None:
    assert MODEL.split(150_000) == {Bucket.SAVINGS: 30_000, Bucket.FIXED: 75_000, Bucket.LEISURE: 45_000}


def test_split_odd_cents_goes_to_largest_remainder() -> None:
    # 1.234,57 €: raw shares 24691.4 / 61728.5 / 37037.1 -> the half cent goes to fixed.
    assert MODEL.split(123_457) == {Bucket.SAVINGS: 24_691, Bucket.FIXED: 61_729, Bucket.LEISURE: 37_037}


@pytest.mark.parametrize("net", [1, 2, 3, 7, 99, 101, 999_999, 123_456_789])
def test_split_always_sums_to_net(net: int) -> None:
    assert sum(MODEL.split(net).values()) == net


def test_budget_model_rejects_shares_not_summing_to_100() -> None:
    with pytest.raises(ValueError, match="100"):
        BudgetModel("x", "x", {Bucket.SAVINGS: 10, Bucket.FIXED: 50, Bucket.LEISURE: 30})


def _closing(fixed: tuple[int, int], leisure: tuple[int, int]) -> tuple[int, int]:
    r = compute_closing(
        {
            Bucket.SAVINGS: BucketStatus(Bucket.SAVINGS, 26_000, 0),
            Bucket.FIXED: BucketStatus(Bucket.FIXED, *fixed),
            Bucket.LEISURE: BucketStatus(Bucket.LEISURE, *leisure),
        }
    )
    return r.reserve_transfer, r.deficit


def test_closing_example_from_brief() -> None:
    assert _closing((65_000, 60_000), (39_000, 30_000)) == (14_000, 0)


def test_closing_nets_overspent_leisure_against_unused_fixed() -> None:
    assert _closing((65_000, 50_000), (39_000, 45_000)) == (9_000, 0)


def test_closing_negative_sum_is_deficit_without_reserve_credit() -> None:
    assert _closing((65_000, 64_000), (39_000, 45_000)) == (0, 5_000)


def test_savings_bucket_is_not_part_of_closing() -> None:
    assert _closing((65_000, 65_000), (39_000, 39_000)) == (0, 0)


def test_basis_points_and_formatting() -> None:
    assert basis_points(17_640, 39_000) == 4523
    assert basis_points(1, 0) is None
    assert format_eur(21_360) == "213,60 €"
    assert format_eur(-123_456_78) == "-123.456,78 €"


def test_pace_example_from_brief() -> None:
    pace = compute_leisure_pace(
        budget=39_000,
        spent=18_000,
        period_start=date(2026, 10, 15),
        today=date(2026, 11, 1),
        expected_payday=date(2026, 11, 15),
    )
    assert pace is not None
    assert (pace.days_left, pace.per_day, pace.per_week) == (14, 1_500, 10_500)


def test_pace_flags_spending_ahead_of_even_distribution() -> None:
    pace = compute_leisure_pace(
        budget=30_000,
        spent=20_000,
        period_start=date(2026, 10, 1),
        today=date(2026, 10, 10),
        expected_payday=date(2026, 10, 31),
    )
    assert pace is not None
    assert pace.planned_spent_by_today == 10_000
    assert pace.ahead_of_plan_by == 10_000


def test_pace_without_remaining_days_is_none() -> None:
    assert (
        compute_leisure_pace(
            budget=1,
            spent=0,
            period_start=date(2026, 1, 1),
            today=date(2026, 2, 1),
            expected_payday=date(2026, 2, 1),
        )
        is None
    )


def test_monthly_equivalent_of_yearly_and_quarterly() -> None:
    assert monthly_equivalent(12_000, Interval.YEARLY) == 1_000
    assert monthly_equivalent(10_000, Interval.QUARTERLY) == 3_333
    assert monthly_equivalent(4_999, Interval.MONTHLY) == 4_999


def test_occurrences_clamp_to_month_end_without_drift() -> None:
    assert occurrences(date(2026, 1, 31), Interval.MONTHLY, date(2026, 2, 1), date(2026, 5, 1)) == [
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
    ]


def test_occurrences_of_yearly_cost_only_in_its_month() -> None:
    assert occurrences(date(2025, 3, 1), Interval.YEARLY, date(2026, 1, 15), date(2026, 2, 15)) == []
    assert occurrences(date(2025, 3, 1), Interval.YEARLY, date(2026, 2, 15), date(2026, 3, 15)) == [
        date(2026, 3, 1)
    ]


def _warnings(leisure_spent: int, **kw: object) -> list[str]:
    ctx = WarningContext(
        leisure=BucketStatus(Bucket.LEISURE, 39_000, leisure_spent),
        fixed=BucketStatus(Bucket.FIXED, 65_000, kw.pop("fixed_spent", 0)),  # type: ignore[arg-type]
        fixed_open_planned=kw.pop("open", 0),  # type: ignore[arg-type]
        reserve_balance=kw.pop("reserve", 0),  # type: ignore[arg-type]
        reserve_minimum=kw.pop("minimum", 0),  # type: ignore[arg-type]
        large_expenses=kw.pop("large", []),  # type: ignore[arg-type]
        pace=None,
    )
    return [w.code for w in evaluate_warnings(ctx)]


def test_warning_thresholds() -> None:
    assert _warnings(29_000) == []
    assert _warnings(29_250) == ["leisure_75"]
    assert _warnings(35_100) == ["leisure_90"]
    assert _warnings(39_001) == ["leisure_exceeded"]


def test_fixed_reserve_and_large_expense_warnings() -> None:
    assert _warnings(0, fixed_spent=40_000, open=30_000) == ["fixed_insufficient"]
    assert _warnings(0, reserve=5_000, minimum=10_000) == ["reserve_low"]  # info: still being built up
    assert _warnings(0, large=[LargeExpense("TV", 80_000)]) == ["large_expense"]
