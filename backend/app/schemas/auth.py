from typing import Annotated

from pydantic import StringConstraints

from app.schemas.common import Schema

Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64, pattern=r"^[\w.\-@]+$")
]
Password = Annotated[str, StringConstraints(min_length=10, max_length=256)]


class SetupIn(Schema):
    username: Username
    password: Password


class LoginIn(Schema):
    username: Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]
    password: Annotated[str, StringConstraints(max_length=256)]


class PasswordChangeIn(Schema):
    current_password: Annotated[str, StringConstraints(max_length=256)]
    new_password: Password


class AuthStatusOut(Schema):
    setup_required: bool
    authenticated: bool
    username: str | None = None
