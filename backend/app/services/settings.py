from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError
from app.domain.budget_models import BUDGET_MODELS
from app.models import AppSettings
from app.schemas.misc import BudgetModelOut, SettingsOut, SettingsUpdate


def get_app_settings(db: Session) -> AppSettings:
    settings = db.get(AppSettings, 1)
    if settings is None:
        settings = AppSettings(id=1)
        db.add(settings)
        db.flush()
    return settings


def settings_out(db: Session) -> SettingsOut:
    s = get_app_settings(db)
    return SettingsOut(
        budget_model_key=s.budget_model_key,
        budget_models=[
            BudgetModelOut(key=m.key, label=m.label, shares_percent=m.shares_percent)
            for m in BUDGET_MODELS.values()
        ],
        reserve_minimum_cents=s.reserve_minimum_cents,
        large_expense_threshold_cents=s.large_expense_threshold_cents,
        reserve_purposes=s.reserve_purposes,
    )


def update_settings(db: Session, data: SettingsUpdate) -> SettingsOut:
    s = get_app_settings(db)
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if "budget_model_key" in fields and fields["budget_model_key"] not in BUDGET_MODELS:
        raise DomainValidationError("Unbekanntes Budgetmodell")
    if "reserve_purposes" in fields:
        fields["reserve_purposes"] = list(dict.fromkeys(fields["reserve_purposes"]))
    for key, value in fields.items():
        setattr(s, key, value)
    db.flush()
    return settings_out(db)
