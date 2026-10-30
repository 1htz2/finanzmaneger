from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.domain.budget_models import Bucket
from app.domain.enums import TransactionType
from app.schemas.transactions import (
    ExpenseIn,
    IncomeIn,
    RecurringSuggestionOut,
    ReverseIn,
    SortField,
    TransactionListOut,
    TransactionOut,
    TransactionUpdate,
    TransferIn,
)
from app.services import transactions as svc
from app.services.idempotency import run_idempotent

router = APIRouter(tags=["transactions"], dependencies=[Depends(current_user)])


@router.get("/transactions", response_model=TransactionListOut)
def list_transactions(
    db: DB,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    bucket: Bucket | None = None,
    type: TransactionType | None = None,
    min_amount: Annotated[int | None, Query(ge=0)] = None,
    max_amount: Annotated[int | None, Query(ge=0)] = None,
    period_id: int | None = None,
    is_recurring: bool | None = None,
    debt_id: int | None = None,
    sort: SortField = "occurred_at",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListOut:
    return svc.list_transactions(
        db,
        q=q,
        date_from=date_from,
        date_to=date_to,
        category_id=category_id,
        bucket=bucket,
        type_=type,
        min_amount=min_amount,
        max_amount=max_amount,
        period_id=period_id,
        is_recurring=is_recurring,
        debt_id=debt_id,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/transactions/recurring-suggestions", response_model=list[RecurringSuggestionOut])
def recurring_suggestions(db: DB) -> list[RecurringSuggestionOut]:
    return svc.recurring_suggestions(db)


class MarkRecurringIn(BaseModel):
    transaction_ids: list[int]
    is_recurring: bool = True


@router.post("/transactions/mark-recurring")
def mark_recurring(data: MarkRecurringIn, db: DB) -> dict[str, int]:
    count = svc.mark_recurring(db, data.transaction_ids, data.is_recurring)
    db.commit()
    return {"updated": count}


@router.get("/transactions/{txn_id}", response_model=TransactionOut)
def get_transaction(txn_id: int, db: DB) -> TransactionOut:
    return svc.to_out(svc.get_transaction(db, txn_id))


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_expense(data: ExpenseIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "expense", data, lambda: svc.create_expense(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.patch("/transactions/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, data: TransactionUpdate, db: DB) -> TransactionOut:
    result = svc.update_transaction(db, txn_id, data)
    db.commit()
    return result


@router.delete("/transactions/{txn_id}", status_code=204)
def delete_transaction(
    txn_id: int,
    db: DB,
    confirm_correction: bool = False,
    correction_reason: Annotated[str | None, Query(max_length=500)] = None,
) -> None:
    svc.delete_transaction(db, txn_id, confirm=confirm_correction, reason=correction_reason)
    db.commit()


@router.post("/transactions/{txn_id}/reverse", response_model=TransactionOut)
def reverse_transaction(txn_id: int, data: ReverseIn, db: DB) -> TransactionOut:
    result = svc.reverse_transaction(
        db, txn_id, confirm=data.confirm_correction, reason=data.correction_reason
    )
    db.commit()
    return result


@router.post("/incomes", response_model=TransactionOut, status_code=201)
def create_income(data: IncomeIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "income", data, lambda: svc.create_income(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.post("/transfers", response_model=TransactionOut, status_code=201)
def create_transfer(data: TransferIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "transfer", data, lambda: svc.create_transfer(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)
