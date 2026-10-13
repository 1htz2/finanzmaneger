from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import clock
from app.core.config import get_settings
from app.db import session as db_session
from app.main import create_app
from app.services.auth import throttle

PASSWORD = "sehr-geheimes-passwort"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    def set(self, iso: str) -> None:
        self.value = datetime.fromisoformat(iso).astimezone(UTC)

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(clock, "now", c)
    return c


class Api:
    """Test client that behaves like the SPA: sends the CSRF header on writes."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def _headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        headers = dict(extra or {})
        csrf = self.client.cookies.get("fm_csrf")
        if csrf:
            headers["X-CSRF-Token"] = csrf
        return headers

    def get(self, url: str, **kw: Any) -> Any:
        return self.client.get(url, **kw)

    def post(self, url: str, json: Any = None, headers: dict[str, str] | None = None, **kw: Any) -> Any:
        return self.client.post(url, json=json, headers=self._headers(headers), **kw)

    def put(self, url: str, json: Any = None, **kw: Any) -> Any:
        return self.client.put(url, json=json, headers=self._headers(None), **kw)

    def patch(self, url: str, json: Any = None, **kw: Any) -> Any:
        return self.client.patch(url, json=json, headers=self._headers(None), **kw)

    def delete(self, url: str, **kw: Any) -> Any:
        return self.client.delete(url, headers=self._headers(None), **kw)

    # ---- domain helpers -------------------------------------------------

    def ok(self, response: Any, status: int = 200) -> Any:
        assert response.status_code == status, response.text
        return response.json() if response.content else None

    def category_id(self, name: str) -> int:
        cats = self.ok(self.get("/api/categories"))
        return next(c["id"] for c in cats if c["name"] == name)

    def salary(self, amount_cents: int, received_at: str, **extra: Any) -> Any:
        return self.ok(
            self.post(
                "/api/salary",
                {"amount_cents": amount_cents, "received_at": received_at, **extra},
            ),
            201,
        )

    def expense(self, amount_cents: int, category: str, occurred_at: str, **extra: Any) -> Any:
        body = {
            "amount_cents": amount_cents,
            "category_id": self.category_id(category),
            "occurred_at": occurred_at,
            "description": extra.pop("description", category),
            **extra,
        }
        return self.ok(self.post("/api/transactions", body), 201)

    def dashboard(self) -> Any:
        return self.ok(self.get("/api/dashboard"))

    def reserve_balance(self) -> int:
        return self.ok(self.get("/api/reserve"))["balance_cents"]

    def savings_balance(self) -> int:
        return self.ok(self.get("/api/savings"))["balance_cents"]


def bucket(summary: dict[str, Any], name: str) -> dict[str, Any]:
    return next(b for b in summary["buckets"] if b["bucket"] == name)


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, frozen: Clock) -> Iterator[TestClient]:
    monkeypatch.setenv("FM_ENV", "test")
    monkeypatch.setenv("FM_SESSION_DAYS", "3650")
    monkeypatch.setenv("FM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FM_FRONTEND_DIST", str(tmp_path / "no-frontend"))
    monkeypatch.delenv("FM_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_session_factory", None)
    throttle._failures.clear()
    app = create_app(get_settings())
    with TestClient(app, base_url="http://testserver") as c:
        yield c
    if db_session._engine is not None:
        db_session._engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def anon(client: TestClient) -> Api:
    return Api(client)


@pytest.fixture
def api(client: TestClient) -> Api:
    a = Api(client)
    a.ok(a.post("/api/auth/setup", {"username": "oskar", "password": PASSWORD}))
    return a
