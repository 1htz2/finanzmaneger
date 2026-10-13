"""Time handling. Everything is stored in UTC; calendar logic uses Europe/Berlin."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Berlin")


def now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Naive datetimes from clients are local (Berlin) wall-clock times."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(UTC)


def local_date(value: datetime) -> date:
    return value.astimezone(LOCAL_TZ).date()


def today() -> date:
    return local_date(now())


def now_default() -> datetime:
    """Column default that resolves ``now`` at call time, so tests can move the clock."""
    return now()
