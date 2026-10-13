from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.services.categories import ensure_default_categories
from app.services.settings import get_app_settings


def ensure_defaults(engine: Engine) -> None:
    """Idempotent: settings row and default categories exist after this runs."""
    with Session(engine) as db:
        get_app_settings(db)
        ensure_default_categories(db)
        db.commit()
