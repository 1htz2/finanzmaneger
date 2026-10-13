from fastapi import APIRouter, Request, Response

from app.api.deps import (
    DB,
    SESSION_COOKIE,
    CurrentUser,
    clear_session_cookies,
    set_session_cookies,
)
from app.schemas.auth import AuthStatusOut, LoginIn, PasswordChangeIn, SetupIn
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusOut)
def status(request: Request, db: DB) -> AuthStatusOut:
    resolved = auth.resolve(db, request.cookies.get(SESSION_COOKIE))
    return AuthStatusOut(
        setup_required=auth.setup_required(db),
        authenticated=resolved is not None,
        username=resolved[0].username if resolved else None,
    )


@router.post("/setup", response_model=AuthStatusOut)
def setup(data: SetupIn, request: Request, response: Response, db: DB) -> AuthStatusOut:
    issued = auth.setup(db, data.username, data.password)
    db.commit()
    set_session_cookies(request, response, issued)
    return AuthStatusOut(setup_required=False, authenticated=True, username=data.username)


@router.post("/login", response_model=AuthStatusOut)
def login(data: LoginIn, request: Request, response: Response, db: DB) -> AuthStatusOut:
    client = request.client.host if request.client else "unknown"
    issued = auth.login(db, data.username, data.password, client)
    db.commit()
    set_session_cookies(request, response, issued)
    return AuthStatusOut(setup_required=False, authenticated=True, username=data.username)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB, _user: CurrentUser) -> None:
    auth.logout(db, request.cookies.get(SESSION_COOKIE))
    db.commit()
    clear_session_cookies(response)


@router.post("/password", status_code=204)
def change_password(data: PasswordChangeIn, request: Request, db: DB, user: CurrentUser) -> None:
    auth.change_password(
        db, user, data.current_password, data.new_password, request.cookies.get(SESSION_COOKIE)
    )
    db.commit()
