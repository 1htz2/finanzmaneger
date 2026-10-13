from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.schemas.periods import (
    CoverDeficitIn,
    ExpectedPaydayIn,
    PeriodDetailOut,
    PeriodSummaryOut,
    SalaryCorrectionIn,
    SalaryIn,
    SalaryPreviewIn,
    SalaryPreviewOut,
    SalaryResultOut,
)
from app.services import periods
from app.services.idempotency import run_idempotent

router = APIRouter(tags=["periods"], dependencies=[Depends(current_user)])


@router.post("/salary/preview", response_model=SalaryPreviewOut)
def preview_salary(data: SalaryPreviewIn, db: DB) -> SalaryPreviewOut:
    return periods.preview_salary(db, data)


@router.post("/salary", response_model=SalaryResultOut, status_code=201)
def record_salary(data: SalaryIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "salary", data, lambda: periods.record_salary(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.get("/periods", response_model=list[PeriodSummaryOut])
def list_periods(db: DB) -> list[PeriodSummaryOut]:
    return periods.list_periods(db)


@router.get("/periods/active", response_model=PeriodDetailOut | None)
def get_active(db: DB) -> PeriodDetailOut | None:
    period = periods.active_period(db)
    return periods.detail(db, period) if period else None


@router.get("/periods/{period_id}", response_model=PeriodDetailOut)
def get_period(period_id: int, db: DB) -> PeriodDetailOut:
    return periods.detail(db, periods.get_period(db, period_id))


@router.put("/periods/active/expected-payday", response_model=PeriodSummaryOut)
def set_expected_payday(data: ExpectedPaydayIn, db: DB) -> PeriodSummaryOut:
    result = periods.set_expected_payday(db, data.expected_next_payday)
    db.commit()
    return result


@router.put("/periods/active/salary", response_model=PeriodSummaryOut)
def correct_salary(data: SalaryCorrectionIn, db: DB) -> PeriodSummaryOut:
    result = periods.correct_active_salary(db, data)
    db.commit()
    return result


@router.post("/periods/{period_id}/cover-deficit", response_model=PeriodDetailOut)
def cover_deficit(
    period_id: int, data: CoverDeficitIn, db: DB, key: IdempotencyKeyHeader = None
) -> JSONResponse:
    body, _ = run_idempotent(
        db,
        key,
        f"cover-deficit:{period_id}",
        data,
        lambda: periods.cover_closed_deficit(db, period_id, data.amount_cents, data.reason),
    )
    db.commit()
    return JSONResponse(body)
