from tests.conftest import Api, Clock, bucket


def _two_periods(api: Api, frozen: Clock) -> None:
    """Period 1 closed with 140 € reserve credit; period 2 active."""
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    api.expense(60_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(30_000, "Restaurants", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    api.salary(150_000, "2026-11-15T09:00:00+01:00")


def _leisure(api: Api) -> dict:
    return bucket(api.dashboard()["active_period"], "leisure")


def test_expense_changes_available_budget_then_edit_and_delete(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    txn = api.expense(2_550, "Lieferdienste", "2026-10-15T20:00:00+02:00", merchant="Lieferando")
    assert txn["bucket"] == "leisure"
    assert _leisure(api)["available_cents"] == 36_450

    edited = api.ok(api.patch(f"/api/transactions/{txn['id']}", {"amount_cents": 4_000}))
    assert edited["amount_cents"] == 4_000
    assert _leisure(api)["available_cents"] == 35_000

    moved = api.ok(
        api.patch(f"/api/transactions/{txn['id']}", {"category_id": api.category_id("Abonnements")})
    )
    assert moved["bucket"] == "fixed"
    assert _leisure(api)["available_cents"] == 39_000
    assert bucket(api.dashboard()["active_period"], "fixed")["available_cents"] == 61_000

    assert api.delete(f"/api/transactions/{txn['id']}").status_code == 204
    assert bucket(api.dashboard()["active_period"], "fixed")["available_cents"] == 65_000
    assert api.get(f"/api/transactions/{txn['id']}").status_code == 404


def test_expense_before_first_salary_is_rejected(api: Api, frozen: Clock) -> None:
    r = api.post(
        "/api/transactions",
        {
            "amount_cents": 100,
            "category_id": api.category_id("Restaurants"),
            "occurred_at": "2026-10-01T10:00:00+02:00",
            "description": "x",
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "no_period_for_date"


def test_same_idempotency_key_creates_one_expense(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    body = {
        "amount_cents": 999,
        "category_id": api.category_id("Restaurants"),
        "occurred_at": "2026-10-15T11:00:00+02:00",
        "description": "Döner",
    }
    a = api.ok(api.post("/api/transactions", body, headers={"Idempotency-Key": "e1"}), 201)
    b = api.ok(api.post("/api/transactions", body, headers={"Idempotency-Key": "e1"}), 201)
    assert a["id"] == b["id"]
    assert api.ok(api.get("/api/transactions", params={"type": "expense"}))["total"] == 1


def test_backdated_expense_in_closed_period_needs_confirmation(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    body = {
        "amount_cents": 2_000,
        "category_id": api.category_id("Kleidung"),
        "occurred_at": "2026-10-25T12:00:00+02:00",
        "description": "Vergessene Ausgabe",
    }
    r = api.post("/api/transactions", body)
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "closed_period_correction_required"
    assert [
        (d["leftover_before_cents"], d["leftover_after_cents"], d["reserve_delta_cents"])
        for d in error["details"]
    ] == [(14_000, 12_000, -2_000)]
    assert api.reserve_balance() == 14_000
    assert api.ok(api.get("/api/transactions", params={"q": "Vergessene"}))["total"] == 0

    api.ok(api.post("/api/transactions", {**body, "confirm_correction": True}), 201)
    assert api.reserve_balance() == 12_000
    closed = api.ok(api.get("/api/periods"))[1]
    detail = api.ok(api.get(f"/api/periods/{closed['id']}"))
    assert [(c["action"], c["reserve_delta_cents"]) for c in detail["corrections"]] == [("create", -2_000)]
    reserve = api.ok(api.get("/api/reserve"))
    assert [(e["kind"], e["amount_cents"]) for e in reserve["entries"]] == [
        ("period_correction", -2_000),
        ("period_close", 14_000),
    ]


def test_correction_that_turns_surplus_into_deficit_removes_whole_credit(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    r = api.post(
        "/api/transactions",
        {
            "amount_cents": 15_000,
            "category_id": api.category_id("Reisen"),
            "occurred_at": "2026-10-25T12:00:00+02:00",
            "description": "Bahnticket",
            "confirm_correction": True,
        },
    )
    api.ok(r, 201)
    assert api.reserve_balance() == 0
    closed = api.ok(api.get("/api/periods"))[1]
    assert closed["deficit_cents"] == 1_000
    assert closed["reserve_transfer_cents"] == 0


def test_deleting_expense_of_closed_period_raises_reserve_after_confirmation(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    rent = api.ok(api.get("/api/transactions", params={"q": "Miete"}))["items"][0]
    assert api.delete(f"/api/transactions/{rent['id']}").status_code == 409
    assert api.reserve_balance() == 14_000
    r = api.delete(f"/api/transactions/{rent['id']}", params={"confirm_correction": True})
    assert r.status_code == 204
    assert api.reserve_balance() == 74_000


def test_moving_expense_from_active_into_closed_period(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    txn = api.expense(5_000, "Restaurants", "2026-11-16T19:00:00+01:00")
    assert _leisure(api)["spent_cents"] == 5_000
    r = api.patch(f"/api/transactions/{txn['id']}", {"occurred_at": "2026-11-10T19:00:00+01:00"})
    assert r.status_code == 409
    api.ok(
        api.patch(
            f"/api/transactions/{txn['id']}",
            {"occurred_at": "2026-11-10T19:00:00+01:00", "confirm_correction": True},
        )
    )
    assert _leisure(api)["spent_cents"] == 0
    assert api.reserve_balance() == 9_000


def test_other_income_targets(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    base = {"occurred_at": "2026-10-15T11:00:00+02:00", "category_id": api.category_id("Geschenk")}
    api.ok(
        api.post("/api/incomes", {**base, "amount_cents": 5_000, "description": "Oma", "target": "period"}),
        201,
    )
    api.ok(
        api.post(
            "/api/incomes", {**base, "amount_cents": 7_000, "description": "Erstattung", "target": "reserve"}
        ),
        201,
    )
    api.ok(
        api.post(
            "/api/incomes", {**base, "amount_cents": 3_000, "description": "Bonus", "target": "savings"}
        ),
        201,
    )
    active = api.dashboard()["active_period"]
    assert _leisure(api)["budget_cents"] == 44_000
    assert active["extra_income_cents"] == 5_000
    assert api.reserve_balance() == 7_000
    assert api.savings_balance() == 29_000
    assert len(api.ok(api.get("/api/periods"))) == 1


def test_salary_category_cannot_be_booked_as_other_income(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    r = api.post(
        "/api/incomes",
        {
            "occurred_at": "2026-10-15T11:00:00+02:00",
            "category_id": api.category_id("Gehalt"),
            "amount_cents": 1,
            "description": "x",
            "target": "period",
        },
    )
    assert r.json()["error"]["code"] == "salary_via_salary_flow"


def test_reversing_income_mirrors_ledger_rows(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    income = api.ok(
        api.post(
            "/api/incomes",
            {
                "occurred_at": "2026-10-15T11:00:00+02:00",
                "amount_cents": 7_000,
                "description": "Erstattung",
                "target": "reserve",
            },
        ),
        201,
    )
    assert api.delete(f"/api/transactions/{income['id']}").json()["error"]["code"] == "use_reversal"
    reversed_ = api.ok(api.post(f"/api/transactions/{income['id']}/reverse", {}))
    assert reversed_["reversed_at"] is not None
    assert api.reserve_balance() == 0
    again = api.post(f"/api/transactions/{income['id']}/reverse", {})
    assert again.json()["error"]["code"] == "already_reversed"
    kinds = [(e["kind"], e["amount_cents"]) for e in api.ok(api.get("/api/reserve"))["entries"]]
    assert kinds == [("reversal", -7_000), ("income", 7_000)]


def test_salary_cannot_be_reversed_or_changed_through_transactions(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    salary_id = api.salary(130_000, "2026-10-15T09:00:00+02:00")["new_period"]["id"]
    txn = api.ok(api.get("/api/transactions", params={"type": "income"}))["items"][0]
    assert salary_id
    assert (
        api.post(f"/api/transactions/{txn['id']}/reverse", {}).json()["error"]["code"]
        == "salary_not_reversible"
    )
    r = api.patch(f"/api/transactions/{txn['id']}", {"amount_cents": 1})
    assert r.json()["error"]["code"] == "immutable_money_fields"
    renamed = api.ok(api.patch(f"/api/transactions/{txn['id']}", {"description": "Gehalt Oktober"}))
    assert renamed["description"] == "Gehalt Oktober"


def test_transfers_move_money_without_creating_any(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    total_before = api.reserve_balance() + api.savings_balance()
    assert total_before == 14_000 + 56_000

    api.ok(
        api.post("/api/transfers", {"from_pot": "reserve", "to_pot": "savings", "amount_cents": 4_000}), 201
    )
    assert (api.reserve_balance(), api.savings_balance()) == (10_000, 60_000)

    api.ok(
        api.post(
            "/api/transfers",
            {"from_pot": "reserve", "to_pot": "period", "bucket": "leisure", "amount_cents": 10_000},
        ),
        201,
    )
    assert api.reserve_balance() == 0
    assert _leisure(api)["budget_cents"] == 55_000

    too_much = api.post("/api/transfers", {"from_pot": "reserve", "to_pot": "savings", "amount_cents": 1})
    assert too_much.json()["error"]["code"] == "reserve_insufficient"

    income_total = api.ok(api.get("/api/transactions", params={"type": "income"}))["income_sum_cents"]
    assert income_total == 130_000 + 150_000
    expense_total = api.ok(api.get("/api/transactions", params={"type": "expense"}))["expense_sum_cents"]
    assert expense_total == 90_000


def test_reversing_transfer_restores_both_pots(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    t = api.ok(
        api.post("/api/transfers", {"from_pot": "savings", "to_pot": "reserve", "amount_cents": 6_000}), 201
    )
    assert (api.reserve_balance(), api.savings_balance()) == (20_000, 50_000)
    api.ok(api.post(f"/api/transactions/{t['id']}/reverse", {}))
    assert (api.reserve_balance(), api.savings_balance()) == (14_000, 56_000)


def test_search_filter_and_sort(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-20T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    api.expense(1_200, "Restaurants", "2026-10-16T12:00:00+02:00", description="Pizza", merchant="Luigi")
    api.expense(4_500, "Kleidung", "2026-10-17T12:00:00+02:00", description="Jeans")
    api.expense(800, "Restaurants", "2026-10-18T12:00:00+02:00", description="Kaffee")

    def descs(**params: object) -> list[str]:
        return [
            t["description"]
            for t in api.ok(api.get("/api/transactions", params={"type": "expense", **params}))["items"]
        ]

    assert descs() == ["Kaffee", "Jeans", "Pizza"]
    assert descs(q="luigi") == ["Pizza"]
    assert descs(category_id=api.category_id("Restaurants")) == ["Kaffee", "Pizza"]
    assert descs(min_amount=1_000, max_amount=2_000) == ["Pizza"]
    assert descs(sort="amount_cents", order="asc") == ["Kaffee", "Pizza", "Jeans"]
    assert descs(date_from="2026-10-17", date_to="2026-10-17") == ["Jeans"]
    assert descs(bucket="leisure", limit=1, offset=1) == ["Jeans"]


def test_recurring_suggestion_and_marking(api: Api, frozen: Clock) -> None:
    _two_periods(api, frozen)
    api.expense(1_299, "Abonnements", "2026-11-16T10:00:00+01:00", description="Netflix", merchant="Netflix")
    frozen.set("2026-12-15T12:00:00+01:00")
    api.salary(150_000, "2026-12-15T09:00:00+01:00")
    api.expense(1_299, "Abonnements", "2026-12-16T10:00:00+01:00", description="Netflix", merchant="Netflix")
    suggestions = api.ok(api.get("/api/transactions/recurring-suggestions"))
    netflix = next(s for s in suggestions if s["label"] == "Netflix")
    assert (netflix["occurrences"], netflix["typical_amount_cents"]) == (2, 1_299)
    api.ok(api.post("/api/transactions/mark-recurring", {"transaction_ids": netflix["transaction_ids"]}))
    marked = api.ok(api.get("/api/transactions", params={"is_recurring": True}))
    assert [t["description"] for t in marked["items"]] == ["Netflix", "Netflix"]
