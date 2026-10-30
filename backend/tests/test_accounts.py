from typing import Any

from tests.conftest import Api, Clock


def _start(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")


def _account(api: Api, name: str, kind: str = "savings_account", **extra: Any) -> dict:
    return api.ok(api.post("/api/accounts", {"name": name, "kind": kind, **extra}), 201)


def _wealth(api: Api) -> dict:
    return api.ok(api.get("/api/wealth"))


def _booked(api: Api) -> dict[str, int]:
    return {a["name"]: a["booked_cents"] for a in _wealth(api)["accounts"]}


def test_salary_savings_rate_is_split_by_shares_and_rest_stays_unassigned(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    _account(api, "ETF-Depot", "brokerage", institution="Trade Republic", savings_share_bp=6_000)
    _account(api, "Tagesgeld", institution="ING", savings_share_bp=3_333)
    api.salary(130_000, "2026-10-15T09:00:00+02:00")  # 260 € savings

    wealth = _wealth(api)
    assert _booked(api) == {"ETF-Depot": 15_600, "Tagesgeld": 8_666}
    assert wealth["unassigned_cents"] == 26_000 - 15_600 - 8_666
    assert wealth["savings_balance_cents"] == 26_000
    assert wealth["shares_total_bp"] == 9_333


def test_salary_correction_keeps_the_proportion(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    _account(api, "Depot", "brokerage", savings_share_bp=5_000)
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    api.ok(api.put("/api/periods/active/salary", {"amount_cents": 150_000, "reason": "Tippfehler"}))
    assert _booked(api) == {"Depot": 15_000}
    assert _wealth(api)["unassigned_cents"] == 15_000


def test_assign_move_and_withdraw_keep_invariants(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    a = _account(api, "Tagesgeld")
    b = _account(api, "Bargeld", "cash")

    too_much = api.post(f"/api/accounts/{a['id']}/assign", {"amount_cents": 26_001})
    assert too_much.json()["error"]["code"] == "savings_location_insufficient"
    api.ok(api.post(f"/api/accounts/{a['id']}/assign", {"amount_cents": 26_000}))
    api.ok(
        api.post(
            "/api/accounts/move",
            {"from_account_id": a["id"], "to_account_id": b["id"], "amount_cents": 6_000},
        )
    )
    assert _booked(api) == {"Tagesgeld": 20_000, "Bargeld": 6_000}

    over = api.post(
        "/api/accounts/move", {"from_account_id": b["id"], "to_account_id": a["id"], "amount_cents": 6_001}
    )
    assert over.json()["error"]["code"] == "account_insufficient"

    # Everything lies somewhere, so a withdrawal has to say where it comes from.
    r = api.post("/api/savings/withdraw", {"amount_cents": 1_000, "reason": "Brille"})
    assert r.json()["error"]["code"] == "savings_location_insufficient"
    api.ok(
        api.post("/api/savings/withdraw", {"amount_cents": 1_000, "reason": "Brille", "account_id": b["id"]}),
        201,
    )
    assert _booked(api) == {"Tagesgeld": 20_000, "Bargeld": 5_000}
    assert _wealth(api)["savings_balance_cents"] == 25_000


def test_transfer_and_income_with_account_and_reversal_mirrors(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    depot = _account(api, "Depot", "brokerage")
    api.ok(api.post("/api/reserve/deposit", {"amount_cents": 50_000, "note": "Start"}), 201)
    txn = api.ok(
        api.post(
            "/api/transfers",
            {"from_pot": "reserve", "to_pot": "savings", "amount_cents": 20_000, "account_id": depot["id"]},
        ),
        201,
    )
    income = api.ok(
        api.post(
            "/api/incomes",
            {
                "amount_cents": 500,
                "description": "Zinsen",
                "occurred_at": "2026-10-15T11:00:00+02:00",
                "target": "savings",
                "account_id": depot["id"],
            },
        ),
        201,
    )
    assert _booked(api) == {"Depot": 20_500}

    api.ok(api.post(f"/api/transactions/{txn['id']}/reverse", {}))
    assert _booked(api) == {"Depot": 500}
    api.ok(api.post(f"/api/transactions/{income['id']}/reverse", {}))
    assert _booked(api) == {"Depot": 0}

    bad = api.post(
        "/api/transfers",
        {
            "from_pot": "reserve",
            "to_pot": "period",
            "bucket": "leisure",
            "amount_cents": 1,
            "account_id": depot["id"],
        },
    )
    assert bad.status_code == 422


def test_valuation_shows_gain_and_wealth_totals(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    depot = _account(api, "ETF", "brokerage", institution="Trade Republic", savings_share_bp=10_000)
    tagesgeld = _account(api, "Tagesgeld", institution="ING", holds_reserve=True)
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    api.ok(api.post("/api/reserve/deposit", {"amount_cents": 100_000, "note": "Start"}), 201)

    valued = api.ok(api.post(f"/api/accounts/{depot['id']}/valuations", {"value_cents": 28_600}), 201)
    assert (valued["booked_cents"], valued["gain_cents"], valued["gain_bp"], valued["value_cents"]) == (
        26_000,
        2_600,
        1_000,
        28_600,
    )

    api.ok(api.post("/api/debts", {"name": "Kredit", "original_cents": 30_000}), 201)

    wealth = _wealth(api)
    assert wealth["reserve_account_id"] == tagesgeld["id"]
    by_name = {a["name"]: a for a in wealth["accounts"]}
    assert by_name["Tagesgeld"]["total_cents"] == 100_000
    assert wealth["gains_cents"] == 2_600
    assert wealth["total_assets_cents"] == 26_000 + 2_600 + 100_000
    assert wealth["net_worth_cents"] == 128_600 - 30_000
    assert [(g["label"], g["total_cents"]) for g in wealth["institutions"]] == [
        ("ING", 100_000),
        ("Trade Republic", 28_600),
    ]


def test_shares_validation_reserve_holder_archive_and_delete(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    a = _account(api, "A", holds_reserve=True)
    b = _account(api, "B", holds_reserve=True)
    holders = [x["name"] for x in _wealth(api)["accounts"] if x["holds_reserve"]]
    assert holders == ["B"]

    r = api.put(
        "/api/accounts/shares",
        {"shares": [{"account_id": a["id"], "share_bp": 6_000}, {"account_id": b["id"], "share_bp": 5_000}]},
    )
    assert r.status_code == 422
    wealth = api.ok(api.put("/api/accounts/shares", {"shares": [{"account_id": a["id"], "share_bp": 7_000}]}))
    assert {x["name"]: x["savings_share_bp"] for x in wealth["accounts"]} == {"A": 7_000, "B": 0}

    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    full = api.patch(f"/api/accounts/{a['id']}", {"archived": True})
    assert full.json()["error"]["code"] == "account_not_empty"
    assert api.delete(f"/api/accounts/{a['id']}").json()["error"]["code"] == "account_has_entries"
    assert api.delete(f"/api/accounts/{b['id']}").status_code == 204

    api.ok(api.post(f"/api/accounts/{a['id']}/assign", {"amount_cents": -18_200}))
    archived = api.ok(api.patch(f"/api/accounts/{a['id']}", {"archived": True}))
    assert (archived["archived"], archived["savings_share_bp"]) == (True, 0)
