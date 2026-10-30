from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import DB, IdempotencyKeyHeader, current_user
from app.schemas.pots import (
    GoalAllocateIn,
    GoalIn,
    GoalOut,
    GoalUpdate,
    ReserveDepositIn,
    ReserveEntryOut,
    ReserveOut,
    ReserveSetupIn,
    ReserveWithdrawIn,
    SavingsEntryOut,
    SavingsOut,
    SavingsWithdrawIn,
)
from app.services import pots
from app.services.idempotency import run_idempotent

router = APIRouter(tags=["pots"], dependencies=[Depends(current_user)])


@router.get("/reserve", response_model=ReserveOut)
def reserve(db: DB) -> ReserveOut:
    return pots.reserve_overview(db)


@router.post("/reserve/deposit", response_model=ReserveEntryOut, status_code=201)
def deposit(data: ReserveDepositIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "reserve-deposit", data, lambda: pots.reserve_deposit(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.post("/reserve/setup", response_model=ReserveOut)
def setup(data: ReserveSetupIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "reserve-setup", data, lambda: pots.reserve_setup(db, data))
    db.commit()
    return JSONResponse(body)


@router.post("/reserve/withdraw", response_model=ReserveEntryOut, status_code=201)
def withdraw(data: ReserveWithdrawIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "reserve-withdraw", data, lambda: pots.reserve_withdraw(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.get("/savings", response_model=SavingsOut)
def savings(db: DB) -> SavingsOut:
    return pots.savings_overview(db)


@router.post("/savings/withdraw", response_model=SavingsEntryOut, status_code=201)
def savings_withdraw(data: SavingsWithdrawIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(db, key, "savings-withdraw", data, lambda: pots.savings_withdraw(db, data))
    db.commit()
    return JSONResponse(body, status_code=201)


@router.get("/savings/goals", response_model=list[GoalOut])
def goals(db: DB, include_archived: bool = False) -> list[GoalOut]:
    return pots.list_goals(db, include_archived)


@router.post("/savings/goals", response_model=GoalOut, status_code=201)
def create_goal(data: GoalIn, db: DB) -> GoalOut:
    result = pots.create_goal(db, data)
    db.commit()
    return result


@router.patch("/savings/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, data: GoalUpdate, db: DB) -> GoalOut:
    result = pots.update_goal(db, goal_id, data)
    db.commit()
    return result


@router.delete("/savings/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: DB) -> None:
    pots.delete_goal(db, goal_id)
    db.commit()


@router.post("/savings/goals/{goal_id}/allocate", response_model=GoalOut)
def allocate(goal_id: int, data: GoalAllocateIn, db: DB, key: IdempotencyKeyHeader = None) -> JSONResponse:
    body, _ = run_idempotent(
        db, key, f"goal-allocate:{goal_id}", data, lambda: pots.allocate_to_goal(db, goal_id, data)
    )
    db.commit()
    return JSONResponse(body)
