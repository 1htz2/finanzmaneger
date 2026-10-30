from tests.conftest import Api, Clock


def _start(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")


def _debt(api: Api, **body: object) -> dict:
    return api.ok(api.post("/api/debts", {"name": "Kredit Auto", "original_cents": 500_000, **body}), 201)


def test_repayment_is_an_expense_and_lowers_remaining(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    debt = _debt(api, creditor="Bank", opening_balance_cents=300_000, monthly_rate_cents=25_000)
    assert (debt["remaining_cents"], debt["progress_bp"], debt["status"]) == (300_000, 4_000, "open")
    assert debt["projected_payoff"] == "2027-10-15"  # 12 rates of 250 €

    api.expense(25_000, "Kredite und Raten", "2026-10-16T10:00:00+02:00", debt_id=debt["id"])
    overview = api.ok(api.get("/api/debts"))
    item = overview["items"][0]
    assert (item["repaid_cents"], item["remaining_cents"], item["repayment_count"]) == (25_000, 275_000, 1)
    assert overview["total_remaining_cents"] == 275_000
    assert overview["repaid_this_period_cents"] == 25_000

    # The rate is ordinary fixed spending: counted once in the budget, no extra pot.
    period = api.dashboard()["active_period"]
    fixed = next(b for b in period["buckets"] if b["bucket"] == "fixed")
    assert fixed["spent_cents"] == 25_000
    assert api.dashboard()["debt_remaining_cents"] == 275_000

    listed = api.ok(api.get("/api/transactions", params={"debt_id": debt["id"]}))
    assert listed["total"] == 1


def test_repayment_cannot_exceed_remaining(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    debt = _debt(api, original_cents=10_000)
    r = api.post(
        "/api/transactions",
        {
            "amount_cents": 10_001,
            "category_id": api.category_id("Kredite und Raten"),
            "occurred_at": "2026-10-16T10:00:00+02:00",
            "description": "Zu viel",
            "debt_id": debt["id"],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "debt_overpaid"

    txn = api.expense(6_000, "Kredite und Raten", "2026-10-16T10:00:00+02:00", debt_id=debt["id"])
    too_much = api.patch(f"/api/transactions/{txn['id']}", {"amount_cents": 10_001})
    assert too_much.json()["error"]["code"] == "debt_overpaid"
    api.ok(api.patch(f"/api/transactions/{txn['id']}", {"amount_cents": 10_000}))
    assert api.ok(api.get("/api/debts"))["items"][0]["status"] == "paid_off"

    # Deleting the expense brings the debt back.
    assert api.delete(f"/api/transactions/{txn['id']}").status_code == 204
    assert api.ok(api.get("/api/debts"))["items"][0]["remaining_cents"] == 10_000


def test_unlinking_and_relinking_a_repayment(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    debt = _debt(api, original_cents=50_000)
    txn = api.expense(20_000, "Sonstige Fixkosten", "2026-10-16T10:00:00+02:00")
    linked = api.ok(api.patch(f"/api/transactions/{txn['id']}", {"debt_id": debt["id"]}))
    assert linked["debt_id"] == debt["id"]
    assert api.ok(api.get("/api/debts"))["items"][0]["remaining_cents"] == 30_000
    api.ok(api.patch(f"/api/transactions/{txn['id']}", {"debt_id": None}))
    assert api.ok(api.get("/api/debts"))["items"][0]["remaining_cents"] == 50_000


def test_planned_rate_becomes_fixed_cost_and_payment_repays_debt(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    debt = _debt(api, monthly_rate_cents=15_000, plan_rate=True, rate_due_date="2026-10-20")
    [rid] = debt["planned_recurring_ids"]
    plan = api.ok(api.get("/api/recurring-expenses"))
    assert [(r["name"], r["amount_cents"], r["debt_id"]) for r in plan] == [
        ("Rate Kredit Auto", 15_000, debt["id"])
    ]

    paid = api.ok(api.post(f"/api/recurring-expenses/{rid}/pay", {}), 201)
    assert paid["debt_id"] == debt["id"]
    assert api.ok(api.get("/api/debts"))["items"][0]["remaining_cents"] == 485_000


def test_delete_only_without_repayments_otherwise_archive(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    unused = _debt(api, name="Privat geliehen", creditor="Anna")
    assert api.delete(f"/api/debts/{unused['id']}").status_code == 204

    debt = _debt(api)
    api.expense(1_000, "Kredite und Raten", "2026-10-16T10:00:00+02:00", debt_id=debt["id"])
    r = api.delete(f"/api/debts/{debt['id']}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "debt_has_repayments"

    archived = api.ok(api.patch(f"/api/debts/{debt['id']}", {"archived": True}))
    assert archived["archived"] is True
    assert api.ok(api.get("/api/debts"))["total_remaining_cents"] == 0
    r = api.post(
        "/api/transactions",
        {
            "amount_cents": 1_000,
            "category_id": api.category_id("Kredite und Raten"),
            "occurred_at": "2026-10-16T11:00:00+02:00",
            "description": "Rate",
            "debt_id": debt["id"],
        },
    )
    assert r.status_code == 422


def test_opening_balance_validation(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    r = api.post("/api/debts", {"name": "X", "original_cents": 1_000, "opening_balance_cents": 2_000})
    assert r.status_code == 422
    debt = _debt(api, original_cents=10_000)
    api.expense(4_000, "Kredite und Raten", "2026-10-16T10:00:00+02:00", debt_id=debt["id"])
    r = api.patch(f"/api/debts/{debt['id']}", {"opening_balance_cents": 3_000})
    assert r.json()["error"]["code"] == "debt_overpaid"
    updated = api.ok(api.patch(f"/api/debts/{debt['id']}", {"monthly_rate_cents": 2_000, "creditor": None}))
    assert (updated["monthly_rate_cents"], updated["remaining_cents"]) == (2_000, 6_000)
