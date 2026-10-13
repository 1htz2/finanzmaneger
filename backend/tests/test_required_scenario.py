"""The binding integration test from the brief (section 19), end to end through the API."""

from tests.conftest import Api, Clock, bucket


def test_two_periods_1300_then_1500(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    first = api.salary(130_000, "2026-10-15T09:00:00+02:00")
    assert first["closed_period"] is None
    p1 = first["new_period"]
    assert bucket(p1, "savings")["budget_cents"] == 26_000
    assert bucket(p1, "fixed")["budget_cents"] == 65_000
    assert bucket(p1, "leisure")["budget_cents"] == 39_000
    assert p1["total_budget_cents"] == 130_000

    api.expense(60_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(30_000, "Restaurants", "2026-10-20T19:00:00+02:00")

    frozen.set("2026-11-15T12:00:00+01:00")
    second = api.salary(150_000, "2026-11-15T09:00:00+01:00")

    closed = second["closed_period"]
    assert closed["status"] == "closed"
    assert bucket(closed, "fixed")["available_cents"] == 5_000
    assert bucket(closed, "leisure")["available_cents"] == 9_000
    assert second["reserve_transfer_cents"] == 14_000
    assert second["deficit_cents"] == 0
    assert bucket(closed, "savings")["budget_cents"] == 26_000

    p2 = second["new_period"]
    assert bucket(p2, "savings")["budget_cents"] == 30_000
    assert bucket(p2, "fixed")["budget_cents"] == 75_000
    assert bucket(p2, "leisure")["budget_cents"] == 45_000
    assert bucket(p2, "fixed")["spent_cents"] == 0
    assert bucket(p2, "leisure")["spent_cents"] == 0

    assert api.reserve_balance() == 14_000
    # 260 € from period 1 stay saved; they are not counted against the new income.
    assert api.savings_balance() == 26_000 + 30_000

    reserve = api.ok(api.get("/api/reserve"))
    assert [(e["kind"], e["amount_cents"]) for e in reserve["entries"]] == [("period_close", 14_000)]

    periods = api.ok(api.get("/api/periods"))
    assert [(p["status"], p["net_salary_cents"]) for p in periods] == [
        ("active", 150_000),
        ("closed", 130_000),
    ]
