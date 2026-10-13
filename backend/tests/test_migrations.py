from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.db.base import Base
from app.db.migrate import upgrade_to_head


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    upgrade_to_head(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_db_rejects_second_active_period(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    upgrade_to_head(url)
    engine = create_engine(url)
    insert = text(
        "INSERT INTO budget_periods (started_at, status, budget_model_key, net_salary_cents, created_at)"
        " VALUES (:s, 'active', '20-50-30', 100, :s)"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"s": "2026-01-01 00:00:00"})
    try:
        with engine.begin() as conn:
            conn.execute(insert, {"s": "2026-02-01 00:00:00"})
        raised = False
    except Exception as exc:
        raised = "UNIQUE" in str(exc)
    engine.dispose()
    assert raised
