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


def split_weighted[K](total: Cents, weights: dict[K, int]) -> dict[K, Cents]:
    """Largest-remainder split of ``total`` by integer weights (in insertion order).

    The parts always add up to ``total`` exactly; ties go to the earlier key."""
    whole = sum(weights.values())
    if whole <= 0:
        raise ValueError("Die Gewichte müssen zusammen größer als 0 sein")
    raw = {k: divmod(total * w, whole) for k, w in weights.items()}
    result = {k: q for k, (q, _) in raw.items()}
    keys = list(weights)
    order = sorted(keys, key=lambda k: (-raw[k][1], keys.index(k)))
    for key in order[: total - sum(result.values())]:
        result[key] += 1
    return result
