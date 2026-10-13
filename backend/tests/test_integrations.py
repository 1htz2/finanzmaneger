from datetime import date

from app.db import session as db_session
from app.integrations.assistant import build_snapshot
from app.integrations.bank_import import BankRow, dedup_key
from tests.conftest import Api, Clock


def test_dedup_key_ignores_whitespace_and_case_but_not_amount() -> None:
    a = BankRow("1234", date(2026, 10, 1), -55_000, "Vermieter GmbH", "Miete Oktober")
    b = BankRow("1234", date(2026, 10, 1), -55_000, "  vermieter   gmbh ", "MIETE oktober")
    c = BankRow("1234", date(2026, 10, 1), -55_001, "Vermieter GmbH", "Miete Oktober")
    assert dedup_key(a) == dedup_key(b)
    assert dedup_key(a) != dedup_key(c)
    assert dedup_key(a).startswith("bank:")


def test_assistant_snapshot_carries_backend_numbers(api: Api, frozen: Clock) -> None:
    frozen.set("2026-10-15T12:00:00+02:00")
    api.salary(130_000, "2026-10-15T09:00:00+02:00")
    api.expense(17_640, "Restaurants", "2026-10-15T11:00:00+02:00")
    assert db_session._session_factory is not None
    with db_session._session_factory() as db:
        snap = build_snapshot(db)
    leisure = next(b for b in snap["active_period"]["buckets"] if b["bucket"] == "leisure")
    assert leisure["available_cents"] == 21_360
    assert snap["category_breakdown_active_period"]["total_cents"] == 17_640
