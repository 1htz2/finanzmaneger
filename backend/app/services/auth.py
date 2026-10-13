"""Single-user authentication with Argon2 hashes and server-side sessions."""

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.errors import AuthError, ConflictError, TooManyRequestsError
from app.models import User, UserSession

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-password")


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    max_age: int


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginThrottle:
    """In-memory lockout after repeated failures. Enough for one local user."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        s = get_settings()
        with self._lock:
            recent = [
                t for t in self._failures.get(key, []) if time.monotonic() - t < s.login_lockout_seconds
            ]
            self._failures[key] = recent
            if len(recent) >= s.login_max_attempts:
                raise TooManyRequestsError(
                    "Zu viele fehlgeschlagene Anmeldeversuche. Bitte warte einige Minuten."
                )

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


throttle = LoginThrottle()


def setup_required(db: Session) -> bool:
    return not db.scalar(select(func.count()).select_from(User))


def issue_session(db: Session, user: User) -> IssuedSession:
    days = get_settings().session_days
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.execute(delete(UserSession).where(UserSession.expires_at < clock.now()))
    db.add(
        UserSession(
            token_hash=_token_hash(token),
            user_id=user.id,
            csrf_token=csrf,
            expires_at=clock.now() + timedelta(days=days),
        )
    )
    db.flush()
    return IssuedSession(token=token, csrf_token=csrf, max_age=days * 86400)


def setup(db: Session, username: str, password: str) -> IssuedSession:
    if not setup_required(db):
        raise ConflictError("Die Anwendung ist bereits eingerichtet.", code="already_set_up")
    user = User(username=username, password_hash=_hasher.hash(password))
    db.add(user)
    db.flush()
    return issue_session(db, user)


def login(db: Session, username: str, password: str, client: str) -> IssuedSession:
    key = f"{client}:{username.lower()}"
    throttle.check(key)
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    try:
        _hasher.verify(user.password_hash if user else _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        throttle.fail(key)
        raise AuthError("Benutzername oder Passwort ist falsch.", code="invalid_credentials") from None
    if user is None:
        throttle.fail(key)
        raise AuthError("Benutzername oder Passwort ist falsch.", code="invalid_credentials")
    throttle.reset(key)
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    return issue_session(db, user)


def resolve(db: Session, token: str | None) -> tuple[User, UserSession] | None:
    if not token:
        return None
    session = db.get(UserSession, _token_hash(token))
    if session is None or session.expires_at <= clock.now():
        return None
    user = db.get(User, session.user_id)
    return (user, session) if user else None


def logout(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))


def change_password(db: Session, user: User, current: str, new: str, keep_token: str | None) -> None:
    try:
        _hasher.verify(user.password_hash, current)
    except (VerificationError, InvalidHashError):
        raise AuthError("Das aktuelle Passwort ist falsch.", code="invalid_credentials") from None
    user.password_hash = _hasher.hash(new)
    keep = _token_hash(keep_token) if keep_token else ""
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != keep))
    db.flush()
