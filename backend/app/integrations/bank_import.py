"""Phase 2: bank statement import (CSV first, FinTS/PSD2 later). Interface plus dedup key.

No bank credentials are requested or stored in v1. An importer produces
``BankRow`` values; the dedup key is stored in ``Transaction.external_ref``
(unique), so importing the same statement twice cannot create duplicates.
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class BankRow:
    account_ref: str  # e.g. last 4 IBAN digits; supports several accounts
    booking_date: date
    amount_cents: int  # negative = money out
    counterparty: str
    purpose: str
    bank_reference: str | None = None  # the bank's own id, when the export has one


class StatementSource(Protocol):
    def rows(self) -> Iterable[BankRow]: ...


class CategoryRule(Protocol):
    """Suggests a category id for a row; the user confirms before booking."""

    def suggest(self, row: BankRow) -> int | None: ...


def dedup_key(row: BankRow) -> str:
    """Stable identity of a bank row, independent of import order or file."""
    if row.bank_reference:
        basis = f"{row.account_ref}|ref|{row.bank_reference}"
    else:
        basis = "|".join(
            [
                row.account_ref,
                row.booking_date.isoformat(),
                str(row.amount_cents),
                " ".join(row.counterparty.lower().split()),
                " ".join(row.purpose.lower().split()),
            ]
        )
    return "bank:" + hashlib.sha256(basis.encode()).hexdigest()[:40]
