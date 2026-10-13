import pytest
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, Api

PROTECTED = [
    ("GET", "/api/dashboard"),
    ("GET", "/api/transactions"),
    ("POST", "/api/transactions"),
    ("PATCH", "/api/transactions/1"),
    ("DELETE", "/api/transactions/1"),
    ("POST", "/api/salary"),
    ("POST", "/api/salary/preview"),
    ("GET", "/api/periods"),
    ("GET", "/api/reserve"),
    ("POST", "/api/reserve/withdraw"),
    ("GET", "/api/savings"),
    ("POST", "/api/transfers"),
    ("POST", "/api/incomes"),
    ("GET", "/api/recurring-expenses"),
    ("GET", "/api/categories"),
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("GET", "/api/stats/overview"),
    ("GET", "/api/export/json"),
    ("POST", "/api/export/backup"),
    ("POST", "/api/auth/logout"),
]


@pytest.mark.parametrize(("method", "url"), PROTECTED)
def test_protected_endpoints_require_login(anon: Api, method: str, url: str) -> None:
    r = anon.client.request(method, url, json={})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_status_setup_login_logout(anon: Api) -> None:
    assert anon.ok(anon.get("/api/auth/status")) == {
        "setup_required": True,
        "authenticated": False,
        "username": None,
    }
    weak = anon.post("/api/auth/setup", {"username": "oskar", "password": "kurz"})
    assert weak.status_code == 422
    anon.ok(anon.post("/api/auth/setup", {"username": "oskar", "password": PASSWORD}))
    assert anon.ok(anon.get("/api/auth/status"))["authenticated"] is True
    again = anon.post("/api/auth/setup", {"username": "mallory", "password": PASSWORD})
    assert again.json()["error"]["code"] == "already_set_up"

    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/dashboard").status_code == 401
    anon.ok(anon.post("/api/auth/login", {"username": "OSKAR", "password": PASSWORD}))
    assert anon.get("/api/dashboard").status_code == 200


def test_session_cookie_flags(client: TestClient) -> None:
    r = client.post("/api/auth/setup", json={"username": "oskar", "password": PASSWORD})
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("fm_session="))
    csrf = next(c for c in cookies if c.startswith("fm_csrf="))
    assert "HttpOnly" in session
    assert "SameSite=strict" in session
    assert "HttpOnly" not in csrf


def test_writes_without_csrf_header_are_forbidden(api: Api) -> None:
    r = api.client.put("/api/settings", json={"reserve_minimum_cents": 1})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"
    r = api.client.put("/api/settings", json={"reserve_minimum_cents": 1}, headers={"X-CSRF-Token": "falsch"})
    assert r.status_code == 403
    assert api.ok(api.put("/api/settings", {"reserve_minimum_cents": 1}))["reserve_minimum_cents"] == 1


def test_wrong_password_and_lockout(anon: Api) -> None:
    anon.ok(anon.post("/api/auth/setup", {"username": "oskar", "password": PASSWORD}))
    anon.post("/api/auth/logout")
    for _ in range(5):
        r = anon.post("/api/auth/login", {"username": "oskar", "password": "falsch-falsch"})
        assert r.status_code == 401
    locked = anon.post("/api/auth/login", {"username": "oskar", "password": PASSWORD})
    assert locked.status_code == 429


def test_password_change_invalidates_other_sessions(api: Api, client: TestClient) -> None:
    other = TestClient(client.app, base_url="http://testserver")
    other.post("/api/auth/login", json={"username": "oskar", "password": PASSWORD})
    assert other.get("/api/dashboard").status_code == 200
    r = api.post("/api/auth/password", {"current_password": PASSWORD, "new_password": "ein-neues-passwort"})
    assert r.status_code == 204
    assert other.get("/api/dashboard").status_code == 401
    assert api.get("/api/dashboard").status_code == 200


def test_api_responses_are_not_cacheable_and_docs_are_off(api: Api) -> None:
    r = api.get("/api/dashboard")
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-frame-options"] == "DENY"
    assert api.get("/api/docs").status_code == 404
    assert api.get("/api/openapi.json").status_code == 404


def test_validation_errors_use_unified_shape(api: Api) -> None:
    r = api.post("/api/transactions", {"amount_cents": -5})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_failed"
    assert {d["field"] for d in body["details"]} >= {"amount_cents", "category_id", "description"}
