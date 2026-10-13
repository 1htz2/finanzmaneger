"""Phase 3: local AI assistant (e.g. Ollama). Snapshot is real; the backend is an interface.

The model only ever receives ``build_snapshot`` output: numbers computed
deterministically by the services. It gets no database session and no write
access, so it can explain and recommend but never invent or change balances.
"""

from typing import Any, Protocol

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.services import insights


def build_snapshot(db: Session) -> dict[str, Any]:
    dash = insights.dashboard(db)
    stats = insights.stats_overview(db, limit=12)
    return jsonable_encoder(
        {
            "currency": "EUR",
            "amounts": "integer cents",
            "active_period": dash.active_period,
            "reserve_balance_cents": dash.reserve_balance_cents,
            "savings": dash.savings,
            "leisure_pace": dash.leisure_pace,
            "warnings": dash.warnings,
            "goals": dash.goals,
            "periods": stats.periods,
            "averages": stats.averages,
            "category_breakdown_active_period": insights.category_breakdown(
                db, period_id=dash.active_period.id
            )
            if dash.active_period
            else None,
        }
    )


class AssistantBackend(Protocol):
    def answer(self, question: str, snapshot: dict[str, Any]) -> str: ...
