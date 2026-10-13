from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.domain.enums import CategoryKind
from app.models import Category, RecurringExpense, Transaction
from app.schemas.misc import CategoryIn, CategoryOut, CategoryUpdate

DEFAULT_CATEGORIES: dict[CategoryKind, list[tuple[str, str]]] = {
    CategoryKind.LEISURE: [
        ("Restaurants", "#f97316"),
        ("Bars und Nachtleben", "#a855f7"),
        ("Kleidung", "#ec4899"),
        ("Lieferdienste", "#ef4444"),
        ("Lebensmittel", "#22c55e"),
        ("Shopping", "#eab308"),
        ("Unterhaltung", "#06b6d4"),
        ("Reisen", "#3b82f6"),
        ("Sonstiges", "#64748b"),
    ],
    CategoryKind.FIXED: [
        ("Miete", "#1d4ed8"),
        ("Krankenversicherung", "#0891b2"),
        ("Handy und Internet", "#7c3aed"),
        ("Fitnessstudio", "#16a34a"),
        ("Abonnements", "#db2777"),
        ("Versicherungen", "#0d9488"),
        ("Strom und Energie", "#ca8a04"),
        ("Mobilität", "#4f46e5"),
        ("Sonstige Fixkosten", "#475569"),
    ],
    CategoryKind.INCOME: [
        ("Gehalt", "#16a34a"),
        ("Erstattung", "#0ea5e9"),
        ("Geschenk", "#f43f5e"),
        ("Nebeneinkommen", "#8b5cf6"),
        ("Sonstige Einnahmen", "#64748b"),
    ],
}


def ensure_default_categories(db: Session) -> None:
    """Seeds the defaults once, into an empty table. User edits are never overwritten."""
    if db.scalar(select(func.count()).select_from(Category)):
        return
    for kind, entries in DEFAULT_CATEGORIES.items():
        for name, color in entries:
            db.add(Category(name=name, kind=kind, color=color, is_default=True))
    db.flush()


def _usage(db: Session) -> dict[int, int]:
    txn = dict(
        db.execute(
            select(Transaction.category_id, func.count())
            .where(Transaction.category_id.is_not(None))
            .group_by(Transaction.category_id)
        ).all()
    )
    rec = dict(
        db.execute(
            select(RecurringExpense.category_id, func.count()).group_by(RecurringExpense.category_id)
        ).all()
    )
    return {k: txn.get(k, 0) + rec.get(k, 0) for k in set(txn) | set(rec)}


def list_categories(db: Session) -> list[CategoryOut]:
    usage = _usage(db)
    rows = db.scalars(select(Category).order_by(Category.kind, Category.archived, Category.name))
    return [
        CategoryOut.model_validate(c).model_copy(update={"usage_count": usage.get(c.id, 0)}) for c in rows
    ]


def _get(db: Session, category_id: int) -> Category:
    c = db.get(Category, category_id)
    if c is None:
        raise NotFoundError("Kategorie nicht gefunden")
    return c


def create_category(db: Session, data: CategoryIn) -> CategoryOut:
    c = Category(name=data.name, kind=data.kind, color=data.color)
    db.add(c)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ConflictError("Eine Kategorie mit diesem Namen gibt es bereits.") from exc
    return CategoryOut.model_validate(c)


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> CategoryOut:
    c = _get(db, category_id)
    if c.kind == CategoryKind.INCOME and c.name == "Gehalt" and data.name not in (None, "Gehalt"):
        raise ConflictError("Die Kategorie „Gehalt“ wird für Gehaltseingänge benötigt.")
    for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(c, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ConflictError("Eine Kategorie mit diesem Namen gibt es bereits.") from exc
    return CategoryOut.model_validate(c).model_copy(update={"usage_count": _usage(db).get(c.id, 0)})


def delete_category(db: Session, category_id: int) -> None:
    c = _get(db, category_id)
    if _usage(db).get(c.id, 0):
        raise ConflictError(
            "Die Kategorie wird verwendet. Archiviere sie stattdessen.", code="category_in_use"
        )
    if c.kind == CategoryKind.INCOME and c.name in ("Gehalt", "Sonstige Einnahmen"):
        raise ConflictError("Diese Kategorie wird vom System benötigt.")
    db.delete(c)
    db.flush()
