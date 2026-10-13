"""Replay protection for mutating requests.

The key row is written in the same database transaction as the operation, and
transactions start with BEGIN IMMEDIATE, so a racing duplicate waits for the
first request to commit and then receives the stored response.
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import IdempotencyKey


def _hash(payload: Any) -> str:
    raw = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def run_idempotent(
    db: Session,
    key: str | None,
    scope: str,
    payload: BaseModel | dict[str, Any] | None,
    operation: Callable[[], Any],
    status_code: int = 200,
) -> tuple[Any, bool]:
    """Returns ``(response_body, replayed)``."""
    if not key:
        return jsonable_encoder(operation()), False
    request_hash = _hash({"scope": scope, "payload": payload})
    existing = db.get(IdempotencyKey, key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ConflictError(
                "Dieser Idempotency-Key wurde bereits für eine andere Anfrage verwendet.",
                code="idempotency_key_reused",
            )
        return existing.response, True
    body = jsonable_encoder(operation())
    db.add(
        IdempotencyKey(
            key=key, scope=scope, request_hash=request_hash, status_code=status_code, response=body
        )
    )
    db.flush()
    return body, False
