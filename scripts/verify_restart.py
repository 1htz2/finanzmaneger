"""Acceptance step 16: data is unchanged after a server restart.

Starts the real server on an empty data directory, books a salary and an expense
over HTTP, stops the server, starts it again and compares the dashboard.

    backend/.venv/Scripts/python scripts/verify_restart.py      (Windows)
    backend/.venv/bin/python scripts/verify_restart.py          (macOS/Linux)
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1] / "backend"
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"


def start(data_dir: str) -> subprocess.Popen[bytes]:
    env = {**os.environ, "FM_DATA_DIR": data_dir, "FM_ENV": "production"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        try:
            if httpx.get(f"{BASE}/api/health").status_code == 200:
                return proc
        except httpx.TransportError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit("server did not start")


def stop(proc: subprocess.Popen[bytes]) -> None:
    # On Windows the venv python is a launcher with a child process; kill the tree.
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        proc.terminate()
    proc.wait(timeout=20)
    for _ in range(50):
        try:
            httpx.get(f"{BASE}/api/health", timeout=0.5)
            time.sleep(0.2)
        except httpx.TransportError:
            return
    raise SystemExit("server still answering after stop: restart check would be meaningless")


def login(client: httpx.Client, setup: bool) -> None:
    path = "/api/auth/setup" if setup else "/api/auth/login"
    r = client.post(path, json={"username": "pruefer", "password": "restart-pruefung-123"})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies["fm_csrf"]


def snapshot(client: httpx.Client) -> dict[str, object]:
    d = client.get("/api/dashboard").json()
    period = d["active_period"]
    return {
        "salary": period["net_salary_cents"],
        "buckets": [(b["bucket"], b["budget_cents"], b["spent_cents"]) for b in period["buckets"]],
        "transactions": client.get("/api/transactions").json()["total"],
        "savings": d["savings"]["balance_cents"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as data_dir:
        proc = start(data_dir)
        try:
            with httpx.Client(base_url=BASE) as c:
                login(c, setup=True)
                r = c.post("/api/salary", json={"amount_cents": 130_000, "received_at": "2026-01-15T09:00:00"})
                assert r.status_code == 201, r.text
                cats = {x["name"]: x["id"] for x in c.get("/api/categories").json()}
                r = c.post(
                    "/api/transactions",
                    json={
                        "amount_cents": 17_640,
                        "category_id": cats["Restaurants"],
                        "occurred_at": "2026-01-16T20:00:00",
                        "description": "Abendessen",
                    },
                )
                assert r.status_code == 201, r.text
                before = snapshot(c)
        finally:
            stop(proc)

        proc = start(data_dir)
        try:
            with httpx.Client(base_url=BASE) as c:
                login(c, setup=False)
                after = snapshot(c)
        finally:
            stop(proc)

    print("before restart:", before)
    print("after restart: ", after)
    assert before == after, "data changed across restart"
    assert after["buckets"] == [("savings", 26_000, 0), ("fixed", 65_000, 0), ("leisure", 39_000, 17_640)]
    print("VERIFIED: data survives a server restart")


if __name__ == "__main__":
    main()
