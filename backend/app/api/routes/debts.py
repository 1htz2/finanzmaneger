from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.schemas.debts import DebtIn, DebtOut, DebtsOverviewOut, DebtUpdate
from app.services import debts
from app.services.idempotency import run_idempotent

router = APIRouter(prefix="/debts", tags=["debts"], dependencies=[Depends(current_user)])


@router.get("", response_model=DebtsOverviewOut)
def overview(db: DB) -> DebtsOverviewOut:
    return debts.overview(db)


@router.post("", response_model=DebtOut, status_code=201)
def create(data: DebtIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "debt-create", data, lambda: debts.create_debt(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.patch("/{debt_id}", response_model=DebtOut)
def update(debt_id: int, data: DebtUpdate, db: DB) -> DebtOut:
    result = debts.update_debt(db, debt_id, data)
    db.commit()
    return result


@router.delete("/{debt_id}", status_code=204)
def delete(debt_id: int, db: DB) -> None:
    debts.delete_debt(db, debt_id)
    db.commit()
