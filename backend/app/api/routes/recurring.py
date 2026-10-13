from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.schemas.recurring import (
    PayRecurringIn,
    RecurringIn,
    RecurringOut,
    RecurringOverviewOut,
    RecurringUpdate,
)
from app.schemas.transactions import TransactionOut
from app.services import recurring
from app.services.idempotency import run_idempotent

router = APIRouter(prefix="/recurring-expenses", tags=["recurring"], dependencies=[Depends(current_user)])


@router.get("", response_model=list[RecurringOut])
def list_recurring(db: DB) -> list[RecurringOut]:
    return recurring.list_recurring(db)


@router.get("/overview", response_model=RecurringOverviewOut)
def overview(db: DB) -> RecurringOverviewOut:
    return recurring.overview(db)


@router.post("", response_model=RecurringOut, status_code=201)
def create(data: RecurringIn, db: DB) -> RecurringOut:
    result = recurring.create_recurring(db, data)
    db.commit()
    return result


@router.patch("/{rid}", response_model=RecurringOut)
def update(rid: int, data: RecurringUpdate, db: DB) -> RecurringOut:
    result = recurring.update_recurring(db, rid, data)
    db.commit()
    return result


@router.delete("/{rid}", status_code=204)
def delete(rid: int, db: DB) -> None:
    recurring.delete_recurring(db, rid)
    db.commit()


@router.post("/{rid}/pay", response_model=TransactionOut, status_code=201)
def pay(rid: int, data: PayRecurringIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(
        db, key, f"pay-recurring:{rid}", data, lambda: recurring.pay_recurring(db, rid, data)
    )
    db.commit()
    return JSONResponse(body, status_code=201)
