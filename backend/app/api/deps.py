import secrets
from typing import Annotated

from fastapi import Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthError, ForbiddenError
from app.db.session import get_db
from app.models import User
from app.services import auth
from app.services.auth import IssuedSession

SESSION_COOKIE = "fm_session"
CSRF_COOKIE = "fm_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

DB = Annotated[Session, Depends(get_db)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


def _secure(request: Request) -> bool:
    mode = get_settings().cookie_secure
    return request.url.scheme == "https" if mode == "auto" else mode == "true"


def set_session_cookies(request: Request, response: Response, issued: IssuedSession) -> None:
    secure = _secure(request)
    response.set_cookie(
        SESSION_COOKIE,
        issued.token,
        max_age=issued.max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    # Readable by the SPA, which echoes it in the X-CSRF-Token header (double submit).
    response.set_cookie(
        CSRF_COOKIE,
        issued.csrf_token,
        max_age=issued.max_age,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def current_user(request: Request, db: DB) -> User:
    resolved = auth.resolve(db, request.cookies.get(SESSION_COOKIE))
    if resolved is None:
        raise AuthError("Bitte melde dich an.")
    user, session = resolved
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not secrets.compare_digest(sent, session.csrf_token):
            raise ForbiddenError("Ungültiges CSRF-Token. Bitte lade die Seite neu.", code="csrf_failed")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
