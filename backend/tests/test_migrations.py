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


def test_debt_migration_keeps_existing_data_and_adds_rate_category(tmp_path: Path) -> None:
    from alembic import command

    from app.db.migrate import alembic_config

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    command.upgrade(alembic_config(url), "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO categories (name, kind, color, is_default, archived, created_at)"
                " VALUES ('Miete', 'fixed', NULL, 1, 0, '2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO budget_periods (started_at, status, budget_model_key, net_salary_cents,"
                " created_at) VALUES ('2026-01-01 00:00:00', 'active', '20-50-30', 100000,"
                " '2026-01-01 00:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (type, occurred_at, amount_cents, bucket, category_id, description,"
                " period_id, is_recurring, source, created_at, updated_at) VALUES ('expense',"
                " '2026-01-02 00:00:00', 50000, 'fixed', 1, 'Miete', 1, 0, 'manual',"
                " '2026-01-02 00:00:00', '2026-01-02 00:00:00')"
            )
        )
    engine.dispose()

    upgrade_to_head(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT amount_cents, debt_id FROM transactions")).all() == [(50000, None)]
        names = conn.execute(text("SELECT name FROM categories WHERE kind = 'fixed' ORDER BY id")).scalars()
        assert list(names) == ["Miete", "Kredite und Raten"]
    engine.dispose()
