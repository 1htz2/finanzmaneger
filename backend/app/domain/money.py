"""Money is always an ``int`` number of euro cents. No floats, ever."""

from decimal import ROUND_HALF_UP, Decimal

Cents = int


def basis_points(part: Cents, whole: Cents) -> int | None:
    """Share of ``part`` in ``whole`` in hundredths of a percent (4523 = 45,23 %)."""
    if whole <= 0:
        return None
    return int((Decimal(part) * 10_000 / Decimal(whole)).quantize(Decimal(1), ROUND_HALF_UP))


def divide_half_up(amount: Cents, divisor: int) -> Cents:
    return int((Decimal(amount) / Decimal(divisor)).quantize(Decimal(1), ROUND_HALF_UP))


def format_eur(cents: Cents) -> str:
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    grouped = f"{euros:,}".replace(",", ".")
    return f"{sign}{grouped},{rest:02d} €"
