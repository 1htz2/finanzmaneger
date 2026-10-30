from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.schemas.accounts import (
    AccountIn,
    AccountOut,
    AccountUpdate,
    AssignIn,
    MoveIn,
    SharesIn,
    ValuationIn,
    WealthOut,
)
from app.services import accounts, wealth
from app.services.idempotency import run_idempotent

router = APIRouter(tags=["accounts"], dependencies=[Depends(current_user)])


@router.get("/wealth", response_model=WealthOut)
def overview(db: DB) -> WealthOut:
    return wealth.overview(db)


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create(data: AccountIn, db: DB) -> AccountOut:
    result = accounts.create_account(db, data)
    db.commit()
    return result


@router.put("/accounts/shares", response_model=WealthOut)
def set_shares(data: SharesIn, db: DB) -> WealthOut:
    accounts.set_shares(db, data)
    db.commit()
    return wealth.overview(db)


@router.post("/accounts/move", response_model=WealthOut)
def move(data: MoveIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    def run() -> WealthOut:
        accounts.move(db, data)
        return wealth.overview(db)

    body, _ = run_idempotent(db, key, "account-move", data, run)
    db.commit()
    return JSONResponse(body)


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update(account_id: int, data: AccountUpdate, db: DB) -> AccountOut:
    result = accounts.update_account(db, account_id, data)
    db.commit()
    return result


@router.delete("/accounts/{account_id}", status_code=204)
def delete(account_id: int, db: DB) -> None:
    accounts.delete_account(db, account_id)
    db.commit()


@router.post("/accounts/{account_id}/assign", response_model=AccountOut)
def assign(account_id: int, data: AssignIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(
        db, key, f"account-assign-{account_id}", data, lambda: accounts.assign(db, account_id, data)
    )
    db.commit()
    return JSONResponse(body)


@router.post("/accounts/{account_id}/valuations", response_model=AccountOut, status_code=201)
def add_valuation(account_id: int, data: ValuationIn, db: DB) -> AccountOut:
    result = accounts.add_valuation(db, account_id, data)
    db.commit()
    return result
