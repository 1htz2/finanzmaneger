from datetime import date

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, Response

from app.api.deps import DB, current_user
from app.core import clock
from app.core.config import get_settings
from app.db.session import get_engine
from app.domain.budget_models import Bucket
from app.schemas.misc import (
    CategoryBreakdownOut,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    DashboardOut,
    SettingsOut,
    SettingsUpdate,
    StatsOverviewOut,
)
from app.services import categories, export, insights
from app.services import settings as settings_svc

router = APIRouter(dependencies=[Depends(current_user)])


@router.get("/dashboard", response_model=DashboardOut, tags=["insights"])
def dashboard(db: DB) -> DashboardOut:
    return insights.dashboard(db)


@router.get("/stats/overview", response_model=StatsOverviewOut, tags=["insights"])
def stats_overview(db: DB) -> StatsOverviewOut:
    return insights.stats_overview(db)


@router.get("/stats/categories", response_model=CategoryBreakdownOut, tags=["insights"])
def stats_categories(
    db: DB,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    bucket: Bucket | None = None,
) -> CategoryBreakdownOut:
    return insights.category_breakdown(
        db, period_id=period_id, date_from=date_from, date_to=date_to, bucket=bucket
    )


@router.get("/categories", response_model=list[CategoryOut], tags=["categories"])
def list_categories(db: DB) -> list[CategoryOut]:
    return categories.list_categories(db)


@router.post("/categories", response_model=CategoryOut, status_code=201, tags=["categories"])
def create_category(data: CategoryIn, db: DB) -> CategoryOut:
    result = categories.create_category(db, data)
    db.commit()
    return result


@router.patch("/categories/{category_id}", response_model=CategoryOut, tags=["categories"])
def update_category(category_id: int, data: CategoryUpdate, db: DB) -> CategoryOut:
    result = categories.update_category(db, category_id, data)
    db.commit()
    return result


@router.delete("/categories/{category_id}", status_code=204, tags=["categories"])
def delete_category(category_id: int, db: DB) -> None:
    categories.delete_category(db, category_id)
    db.commit()


@router.get("/settings", response_model=SettingsOut, tags=["settings"])
def get_settings_route(db: DB) -> SettingsOut:
    return settings_svc.settings_out(db)


@router.put("/settings", response_model=SettingsOut, tags=["settings"])
def update_settings(data: SettingsUpdate, db: DB) -> SettingsOut:
    result = settings_svc.update_settings(db, data)
    db.commit()
    return result


def _stamp() -> str:
    return clock.now().astimezone(clock.LOCAL_TZ).strftime("%Y-%m-%d")


@router.get("/export/json", tags=["export"])
def export_json(db: DB) -> JSONResponse:
    return JSONResponse(
        jsonable_encoder(export.export_json(db)),
        headers={"Content-Disposition": f'attachment; filename="finanzmanager-{_stamp()}.json"'},
    )


@router.get("/export/transactions.csv", tags=["export"])
def export_csv(db: DB) -> Response:
    return Response(
        export.transactions_csv(db),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="buchungen-{_stamp()}.csv"'},
    )


@router.post("/export/backup", tags=["export"])
def create_backup() -> FileResponse:
    path = export.backup_sqlite(get_engine(), get_settings().backup_dir)
    return FileResponse(path, filename=path.name, media_type="application/vnd.sqlite3")
