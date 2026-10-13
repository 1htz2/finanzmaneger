from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core import clock

MAX_CENTS = 100_000_000_00  # 100 Mio. € — far beyond any personal transaction

PositiveCents = Annotated[int, Field(gt=0, le=MAX_CENTS)]
NonNegativeCents = Annotated[int, Field(ge=0, le=MAX_CENTS)]
SignedCents = Annotated[int, Field(ge=-MAX_CENTS, le=MAX_CENTS)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
# Naive client datetimes are Berlin wall-clock time; everything is normalized to UTC.
Instant = Annotated[datetime, AfterValidator(clock.as_utc)]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CorrectionConfirmation(Schema):
    """Sent with changes that may touch a closed period (brief 4.2)."""

    confirm_correction: bool = False
    correction_reason: OptionalText = None
