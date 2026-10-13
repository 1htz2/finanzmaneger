"""Data export and SQLite backups. Nothing leaves the machine unless the user downloads it."""

import csv
import io
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from app.core import clock
from app.domain.money import format_eur
from app.models import (
    AppSettings,
    BudgetAllocation,
    BudgetPeriod,
    Category,
    PeriodCorrection,
    RecurringExpense,
    ReserveEntry,
    SavingsAllocation,
    SavingsEntry,
    SavingsGoal,
    Transaction,
)

EXPORTED = (
    AppSettings,
    Category,
    BudgetPeriod,
    BudgetAllocation,
    Transaction,
    RecurringExpense,
    ReserveEntry,
    SavingsEntry,
    SavingsGoal,
    SavingsAllocation,
    PeriodCorrection,
)

TYPE_LABELS = {"expense": "Ausgabe", "income": "Einnahme", "transfer": "Umbuchung"}


def export_json(db: Session) -> dict[str, Any]:
    data: dict[str, Any] = {
        "format": "finanzmanager-export",
        "version": 1,
        "exported_at": clock.now().isoformat(),
        "currency": "EUR",
        "amounts": "integer cents",
    }
    for model in EXPORTED:
        columns = [c.key for c in inspect(model).mapper.column_attrs]
        data[model.__tablename__] = [
            {c: getattr(row, c) for c in columns} for row in db.scalars(select(model)).unique()
        ]
    return data


def transactions_csv(db: Session) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "ID",
            "Datum",
            "Typ",
            "Betrag",
            "Betrag (Cent)",
            "Topf",
            "Kategorie",
            "Beschreibung",
            "Händler",
            "Periode",
            "Storniert",
        ]
    )
    rows = db.scalars(select(Transaction).order_by(Transaction.occurred_at)).unique()
    for t in rows:
        writer.writerow(
            [
                t.id,
                t.occurred_at.astimezone(clock.LOCAL_TZ).strftime("%d.%m.%Y %H:%M"),
                TYPE_LABELS[t.type.value],
                format_eur(t.amount_cents),
                t.amount_cents,
                t.bucket.value if t.bucket else "",
                t.category.name if t.category else "",
                t.description,
                t.merchant or "",
                t.period_id or "",
                "ja" if t.reversed_at else "",
            ]
        )
    return "﻿" + buffer.getvalue()


def backup_sqlite(engine: Engine, target_dir: Path) -> Path:
    """Consistent online snapshot via SQLite's backup API (safe while the app runs)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"finanzmanager-{clock.now().strftime('%Y%m%d-%H%M%S')}.db"
    raw = engine.raw_connection()
    try:
        source = raw.driver_connection
        assert isinstance(source, sqlite3.Connection)
        with sqlite3.connect(target) as dest:
            source.backup(dest)
        dest.close()
    finally:
        raw.close()
    return target
