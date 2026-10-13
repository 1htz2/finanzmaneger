from tests.conftest import Api, Clock


def _start(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")


def test_reserve_deposit_withdraw_and_history(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.ok(api.post("/api/reserve/deposit", {"amount_cents": 50_000, "note": "Bargeld"}), 201)
    too_much = api.post(
        "/api/reserve/withdraw", {"amount_cents": 60_000, "purpose": "Reparaturen", "reason": "Fahrrad"}
    )
    assert too_much.json()["error"]["code"] == "reserve_insufficient"
    api.ok(
        api.post(
            "/api/reserve/withdraw",
            {"amount_cents": 12_000, "purpose": "Reparaturen", "reason": "Fahrrad"},
        ),
        201,
    )
    reserve = api.ok(api.get("/api/reserve"))
    assert reserve["balance_cents"] == 38_000
    assert reserve["total_withdrawn_cents"] == 12_000
    assert [p["balance_cents"] for p in reserve["history"]] == [50_000, 38_000]
    assert reserve["entries"][0]["purpose"] == "Reparaturen"
    assert "Notfälle" in reserve["purposes"]


def test_goals_earmark_savings_without_double_counting(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    goal = api.ok(api.post("/api/savings/goals", {"title": "Laptop", "target_cents": 200_000}), 201)
    api.ok(api.post(f"/api/savings/goals/{goal['id']}/allocate", {"amount_cents": 20_000}))
    over = api.post(f"/api/savings/goals/{goal['id']}/allocate", {"amount_cents": 6_001})
    assert over.json()["error"]["code"] == "savings_insufficient"

    savings = api.ok(api.get("/api/savings"))
    assert (savings["balance_cents"], savings["allocated_cents"], savings["unallocated_cents"]) == (
        26_000,
        20_000,
        6_000,
    )
    assert savings["goals"][0]["progress_bp"] == 1_000
    assert savings["goals"][0]["remaining_cents"] == 180_000
    dash = api.dashboard()["savings"]
    assert dash["balance_cents"] == 26_000

    api.ok(
        api.post("/api/savings/withdraw", {"amount_cents": 15_000, "reason": "Kauf", "goal_id": goal["id"]}),
        201,
    )
    savings = api.ok(api.get("/api/savings"))
    assert (savings["balance_cents"], savings["allocated_cents"]) == (11_000, 5_000)


def test_goal_projection_uses_own_pace(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    goal = api.ok(api.post("/api/savings/goals", {"title": "Urlaub", "target_cents": 20_000}), 201)
    api.ok(api.post(f"/api/savings/goals/{goal['id']}/allocate", {"amount_cents": 10_000}))
    assert api.ok(api.get("/api/savings/goals"))[0]["projected_date"] is None
    frozen.set("2026-10-25T12:00:00+02:00")
    # 100 € in 10 days -> remaining 100 € takes 10 more days.
    assert api.ok(api.get("/api/savings/goals"))[0]["projected_date"] == "2026-11-04"


def test_deleting_goal_frees_money(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    goal = api.ok(api.post("/api/savings/goals", {"title": "X", "target_cents": 1_000}), 201)
    api.ok(api.post(f"/api/savings/goals/{goal['id']}/allocate", {"amount_cents": 1_000}))
    assert api.delete(f"/api/savings/goals/{goal['id']}").status_code == 204
    assert api.ok(api.get("/api/savings"))["unallocated_cents"] == 26_000


def _recurring(api: Api, name: str, amount: int, interval: str, due: str | None, category: str) -> dict:
    body = {
        "name": name,
        "amount_cents": amount,
        "interval": interval,
        "category_id": api.category_id(category),
    }
    if due:
        body["due_date"] = due
    return api.ok(api.post("/api/recurring-expenses", body), 201)


def test_planned_fixed_costs_are_not_counted_twice(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.ok(api.put("/api/periods/active/expected-payday", {"expected_next_payday": "2026-11-15"}))
    rent = _recurring(api, "Miete", 55_000, "monthly", "2026-11-01", "Miete")
    _recurring(api, "Handy", 2_000, "monthly", None, "Handy und Internet")
    yearly = _recurring(api, "Software", 12_000, "yearly", "2027-03-01", "Abonnements")
    assert yearly["monthly_equivalent_cents"] == 1_000

    ov = api.ok(api.get("/api/recurring-expenses/overview"))
    assert ov["window_estimated"] is False
    assert (ov["planned_in_period_cents"], ov["open_in_period_cents"], ov["fixed_spent_cents"]) == (
        57_000,
        57_000,
        0,
    )
    assert ov["monthly_total_cents"] == 55_000 + 2_000 + 1_000
    assert ov["yearly_total_cents"] == 660_000 + 24_000 + 12_000
    assert ov["sufficient"] is True

    paid = api.ok(
        api.post(f"/api/recurring-expenses/{rent['id']}/pay", {"occurred_at": "2026-11-01T08:00:00+01:00"}),
        201,
    )
    assert paid["recurring_expense_id"] == rent["id"]
    ov = api.ok(api.get("/api/recurring-expenses/overview"))
    assert (
        ov["planned_in_period_cents"],
        ov["paid_in_period_cents"],
        ov["open_in_period_cents"],
        ov["fixed_spent_cents"],
    ) == (
        57_000,
        55_000,
        2_000,
        55_000,
    )
    assert api.dashboard()["fixed_open_cents"] == 2_000


def test_fixed_budget_insufficient_warning(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    _recurring(api, "Miete", 70_000, "monthly", None, "Miete")
    ov = api.ok(api.get("/api/recurring-expenses/overview"))
    assert (ov["sufficient"], ov["shortfall_cents"]) == (False, 5_000)
    codes = [w["code"] for w in api.dashboard()["warnings"]]
    assert "fixed_insufficient" in codes


def test_recurring_requires_fixed_category(api: Api, frozen: Clock) -> None:
    r = api.post(
        "/api/recurring-expenses",
        {
            "name": "x",
            "amount_cents": 1,
            "interval": "monthly",
            "category_id": api.category_id("Restaurants"),
        },
    )
    assert r.status_code == 422


def test_custom_category_lifecycle(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    cat = api.ok(
        api.post("/api/categories", {"name": "Haustier", "kind": "leisure", "color": "#123456"}), 201
    )
    dup = api.post("/api/categories", {"name": "Haustier", "kind": "leisure"})
    assert dup.status_code == 409
    api.expense(1_000, "Haustier", "2026-10-15T11:00:00+02:00")
    in_use = api.delete(f"/api/categories/{cat['id']}")
    assert in_use.json()["error"]["code"] == "category_in_use"
    archived = api.ok(api.patch(f"/api/categories/{cat['id']}", {"archived": True}))
    assert archived["archived"] is True
    assert archived["usage_count"] == 1


def test_stats_compare_periods_and_savings_rate(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(60_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(30_000, "Restaurants", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    api.salary(150_000, "2026-11-15T09:00:00+01:00")
    stats = api.ok(api.get("/api/stats/overview"))
    assert [p["net_salary_cents"] for p in stats["periods"]] == [130_000, 150_000]
    closed = stats["periods"][0]
    # (1300 - 900) / 1300 = 30,77 % actual vs. 20 % planned
    assert (closed["actual_savings_rate_bp"], closed["planned_savings_rate_bp"]) == (3077, 2000)
    assert stats["periods"][1]["actual_savings_rate_bp"] is None
    assert stats["averages"]["avg_leisure_spent_cents"] == 30_000
    assert [p["balance_cents"] for p in stats["reserve_history"]] == [14_000]

    cats = api.ok(api.get("/api/stats/categories", params={"period_id": closed["id"]}))
    assert [(i["category"]["name"], i["total_cents"], i["share_bp"]) for i in cats["items"]] == [
        ("Miete", 60_000, 6667),
        ("Restaurants", 30_000, 3333),
    ]


def test_exports(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(1_234, "Restaurants", "2026-10-15T11:00:00+02:00", description="Mittag")
    csv = api.get("/api/export/transactions.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    assert "Mittag" in csv.text
    assert "12,34 €" in csv.text
    data = api.ok(api.get("/api/export/json"))
    assert len(data["budget_periods"]) == 1
    assert "users" not in data
    backup = api.post("/api/export/backup")
    assert backup.status_code == 200
    assert backup.content[:16] == b"SQLite format 3\x00"
