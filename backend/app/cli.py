"""Admin commands: ``python -m app.cli <command>``.

backup                    consistent SQLite snapshot into <data>/backups
restore <file>            replace the database with a backup (stop the server first)
reset-password <user>     set a new password (prompts) and end all sessions
migrate                   apply database migrations
seed-demo                 fill an EMPTY database with clearly labelled demo data
"""

import argparse
import getpass
import shutil
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.db.migrate import upgrade_to_head
from app.db.session import get_engine
from app.models import BudgetPeriod, User, UserSession
from app.services import export
from app.services.bootstrap import ensure_defaults


def _db_file() -> Path:
    url = get_settings().sqlalchemy_url
    if not url.startswith("sqlite:///"):
        sys.exit("Nur SQLite-Datenbanken werden unterstützt.")
    return Path(url.removeprefix("sqlite:///"))


def cmd_backup(_: argparse.Namespace) -> None:
    path = export.backup_sqlite(get_engine(), get_settings().backup_dir)
    print(f"Backup erstellt: {path}")


def cmd_restore(args: argparse.Namespace) -> None:
    source = Path(args.file)
    with sqlite3.connect(source) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            sys.exit("Die Backup-Datei ist beschädigt.")
    target = _db_file()
    if target.exists():
        safety = target.with_suffix(f".vor-restore-{clock.now().strftime('%Y%m%d-%H%M%S')}.db")
        shutil.copy2(target, safety)
        print(f"Bisherige Datenbank gesichert: {safety}")
    for suffix in ("-wal", "-shm"):
        Path(f"{target}{suffix}").unlink(missing_ok=True)
    shutil.copy2(source, target)
    upgrade_to_head(get_settings().sqlalchemy_url)
    print(f"Wiederhergestellt aus {source}")


def cmd_reset_password(args: argparse.Namespace) -> None:
    from app.services.auth import _hasher

    password = getpass.getpass("Neues Passwort (mind. 10 Zeichen): ")
    if len(password) < 10 or password != getpass.getpass("Wiederholen: "):
        sys.exit("Passwort zu kurz oder nicht identisch.")
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(func.lower(User.username) == args.username.lower()))
        if user is None:
            sys.exit("Benutzer nicht gefunden.")
        user.password_hash = _hasher.hash(password)
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        db.commit()
    print("Passwort geändert. Alle Sitzungen wurden beendet.")


def cmd_migrate(_: argparse.Namespace) -> None:
    upgrade_to_head(get_settings().sqlalchemy_url)
    ensure_defaults(get_engine())
    print("Datenbank ist aktuell.")


def cmd_seed_demo(_: argparse.Namespace) -> None:
    """Demo data goes through the same services as real input, so it obeys every rule."""
    from app.domain.recurring import Interval
    from app.schemas.periods import SalaryIn
    from app.schemas.pots import GoalAllocateIn, GoalIn
    from app.schemas.recurring import RecurringIn
    from app.schemas.transactions import ExpenseIn
    from app.services import categories, periods, pots, recurring
    from app.services.transactions import create_expense

    upgrade_to_head(get_settings().sqlalchemy_url)
    ensure_defaults(get_engine())
    with Session(get_engine()) as db:
        if db.scalar(select(func.count()).select_from(BudgetPeriod)):
            sys.exit("Die Datenbank enthält bereits Budgetzeiträume. Demo-Daten nur in eine leere DB.")
        cats = {c.name: c.id for c in categories.list_categories(db)}
        now = clock.now()
        rent = recurring.create_recurring(
            db,
            RecurringIn(
                name="Miete (Demo)",
                amount_cents=55_000,
                category_id=cats["Miete"],
                interval=Interval.MONTHLY,
                due_date=(now - timedelta(days=75)).date(),
            ),
        )
        starts = [now - timedelta(days=d) for d in (75, 45, 14)]
        spending = [
            [
                ("Miete", 55_000),
                ("Handy und Internet", 2_000),
                ("Restaurants", 8_450),
                ("Lebensmittel", 12_000),
                ("Kleidung", 6_999),
            ],
            [
                ("Miete", 55_000),
                ("Krankenversicherung", 4_000),
                ("Bars und Nachtleben", 9_500),
                ("Lebensmittel", 13_200),
                ("Reisen", 18_000),
            ],
            [("Miete", 55_000), ("Lieferdienste", 3_890), ("Lebensmittel", 7_640), ("Unterhaltung", 2_499)],
        ]
        for start, salary, items in zip(starts, (130_000, 145_000, 138_000), spending, strict=True):
            periods.record_salary(
                db, SalaryIn(amount_cents=salary, received_at=start, description="Gehalt (Demo)")
            )
            for i, (name, amount) in enumerate(items):
                booked_at = start + timedelta(days=1 + i * 3, hours=3)
                if booked_at > now:
                    continue
                create_expense(
                    db,
                    ExpenseIn(
                        occurred_at=booked_at,
                        amount_cents=amount,
                        category_id=cats[name],
                        description=f"{name} (Demo)",
                        recurring_expense_id=rent.id if name == "Miete" else None,
                    ),
                )
        periods.set_expected_payday(db, clock.today() + timedelta(days=16))
        recurring.create_recurring(
            db,
            RecurringIn(
                name="Haftpflicht (Demo)",
                amount_cents=6_000,
                category_id=cats["Versicherungen"],
                interval=Interval.YEARLY,
            ),
        )
        goal = pots.create_goal(db, GoalIn(title="Neuer Laptop (Demo)", target_cents=200_000))
        pots.allocate_to_goal(db, goal.id, GoalAllocateIn(amount_cents=40_000))
        db.commit()
    print("Demo-Daten angelegt. Alle Einträge sind mit „(Demo)“ markiert.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="FinanzManager Verwaltung")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backup").set_defaults(func=cmd_backup)
    restore = sub.add_parser("restore")
    restore.add_argument("file")
    restore.set_defaults(func=cmd_restore)
    reset = sub.add_parser("reset-password")
    reset.add_argument("username")
    reset.set_defaults(func=cmd_reset_password)
    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    sub.add_parser("seed-demo").set_defaults(func=cmd_seed_demo)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
