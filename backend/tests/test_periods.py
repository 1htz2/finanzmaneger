import threading

from fastapi.testclient import TestClient

from tests.conftest import Api, Clock, bucket


def _start(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")


def test_first_salary_opens_single_active_period(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    active = api.ok(api.get("/api/periods/active"))
    assert active["status"] == "active"
    assert active["ended_at"] is None
    assert [(a["bucket"], a["amount_cents"], a["source"]) for a in active["allocations"]] == [
        ("savings", 26_000, "salary"),
        ("fixed", 65_000, "salary"),
        ("leisure", 39_000, "salary"),
    ]
    assert api.savings_balance() == 26_000


def test_same_idempotency_key_creates_one_period_and_one_reserve_credit(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(10_000, "Restaurants", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    body = {"amount_cents": 150_000, "received_at": "2026-11-15T09:00:00+01:00"}
    headers = {"Idempotency-Key": "salary-2026-11"}
    first = api.ok(api.post("/api/salary", body, headers=headers), 201)
    second = api.ok(api.post("/api/salary", body, headers=headers), 201)
    assert first == second
    assert len(api.ok(api.get("/api/periods"))) == 2
    assert api.reserve_balance() == 94_000
    assert api.savings_balance() == 56_000


def test_idempotency_key_reused_with_other_payload_is_rejected(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    frozen.set("2026-11-15T12:00:00+01:00")
    headers = {"Idempotency-Key": "k1"}
    api.ok(
        api.post(
            "/api/salary",
            {"amount_cents": 1_000, "received_at": "2026-11-15T09:00:00+01:00"},
            headers=headers,
        ),
        201,
    )
    r = api.post(
        "/api/salary", {"amount_cents": 2_000, "received_at": "2026-11-15T09:00:00+01:00"}, headers=headers
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "idempotency_key_reused"


def test_duplicate_salary_without_key_is_rejected(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    r = api.post("/api/salary", {"amount_cents": 130_000, "received_at": "2026-10-15T09:00:00+02:00"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "salary_before_active_period"
    assert len(api.ok(api.get("/api/periods"))) == 1


def test_concurrent_double_submit_yields_one_transition(client: TestClient, api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    frozen.set("2026-11-15T12:00:00+01:00")
    body = {"amount_cents": 150_000, "received_at": "2026-11-15T09:00:00+01:00"}
    statuses: list[int] = []

    def submit() -> None:
        statuses.append(api.post("/api/salary", body, headers={"Idempotency-Key": "race"}).status_code)

    threads = [threading.Thread(target=submit) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert statuses == [201, 201, 201, 201]
    periods = api.ok(api.get("/api/periods"))
    assert [p["status"] for p in periods] == ["active", "closed"]
    assert api.reserve_balance() == 65_000 + 39_000


def test_salary_in_future_is_rejected(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    r = api.post("/api/salary", {"amount_cents": 1_000, "received_at": "2026-10-16T09:00:00+02:00"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "salary_in_future"


def test_preview_matches_recorded_result_and_changes_nothing(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(60_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(30_000, "Restaurants", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    body = {"amount_cents": 150_000, "received_at": "2026-11-15T09:00:00+01:00"}
    preview = api.ok(api.post("/api/salary/preview", body))
    assert preview["closing"]["reserve_transfer_cents"] == 14_000
    assert preview["reserve_balance_before_cents"] == 0
    assert preview["reserve_balance_after_cents"] == 14_000
    assert preview["savings_balance_after_cents"] == 56_000
    assert [(s["bucket"], s["amount_cents"]) for s in preview["new_split"]] == [
        ("savings", 30_000),
        ("fixed", 75_000),
        ("leisure", 45_000),
    ]
    assert len(api.ok(api.get("/api/periods"))) == 1
    assert api.reserve_balance() == 0

    result = api.salary(**body)
    assert result["reserve_transfer_cents"] == preview["closing"]["reserve_transfer_cents"]


def test_overspent_period_shows_deficit_and_no_reserve_credit(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(65_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(45_000, "Reisen", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    result = api.salary(150_000, "2026-11-15T09:00:00+01:00")
    assert result["reserve_transfer_cents"] == 0
    assert result["deficit_cents"] == 6_000
    assert result["closed_period"]["deficit_cents"] == 6_000
    assert api.reserve_balance() == 0


def test_deficit_is_covered_from_reserve_only_when_requested(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.ok(api.post("/api/reserve/deposit", {"amount_cents": 10_000, "note": "Startguthaben"}), 201)
    api.expense(65_000, "Miete", "2026-10-16T10:00:00+02:00")
    api.expense(45_000, "Reisen", "2026-10-20T19:00:00+02:00")
    frozen.set("2026-11-15T12:00:00+01:00")
    result = api.salary(150_000, "2026-11-15T09:00:00+01:00", cover_deficit_from_reserve=True)
    assert result["deficit_covered_cents"] == 6_000
    assert result["deficit_cents"] == 0
    assert result["closed_period"]["transfer_net_cents"] == 6_000
    assert api.reserve_balance() == 4_000


def test_expenses_dated_after_new_salary_move_to_new_period(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    frozen.set("2026-11-16T12:00:00+01:00")
    api.expense(2_000, "Restaurants", "2026-11-15T20:00:00+01:00")
    result = api.salary(150_000, "2026-11-15T09:00:00+01:00")
    assert bucket(result["closed_period"], "leisure")["spent_cents"] == 0
    assert bucket(result["new_period"], "leisure")["spent_cents"] == 2_000
    assert result["reserve_transfer_cents"] == 104_000


def test_correct_active_salary_books_deltas(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    summary = api.ok(api.put("/api/periods/active/salary", {"amount_cents": 140_000, "reason": "Tippfehler"}))
    assert summary["net_salary_cents"] == 140_000
    assert [bucket(summary, b)["budget_cents"] for b in ("savings", "fixed", "leisure")] == [
        28_000,
        70_000,
        42_000,
    ]
    assert api.savings_balance() == 28_000


def test_expected_payday_drives_weekly_guidance(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    frozen.set("2026-11-01T12:00:00+01:00")
    api.expense(18_000, "Restaurants", "2026-10-20T19:00:00+02:00")
    assert api.dashboard()["leisure_pace"] is None
    assert api.dashboard()["pace_unavailable_reason"] == "no_expected_payday"
    api.ok(api.put("/api/periods/active/expected-payday", {"expected_next_payday": "2026-11-15"}))
    pace = api.dashboard()["leisure_pace"]
    assert (pace["days_left"], pace["per_day_cents"], pace["per_week_cents"]) == (14, 1_500, 10_500)
    leisure = bucket(api.dashboard()["active_period"], "leisure")
    assert leisure["available_cents"] == 21_000


def test_dashboard_example_from_brief(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(17_640, "Restaurants", "2026-10-15T20:00:00+02:00")
    leisure = bucket(api.dashboard()["active_period"], "leisure")
    assert (
        leisure["budget_cents"],
        leisure["spent_cents"],
        leisure["available_cents"],
        leisure["used_bp"],
    ) == (
        39_000,
        17_640,
        21_360,
        4523,
    )


def test_large_expense_warning_ignores_fixed_costs(api: Api, frozen: Clock) -> None:
    _start(api, frozen)
    api.expense(60_000, "Miete", "2026-10-15T10:00:00+02:00", description="Miete")
    api.expense(20_000, "Reisen", "2026-10-15T11:00:00+02:00", description="Flug")
    large = [w["message"] for w in api.dashboard()["warnings"] if w["code"] == "large_expense"]
    assert large == ["Flug: 200,00 €"]
