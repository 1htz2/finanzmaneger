"""Phase 2: payslip upload. Interface only.

Flow once implemented: upload PDF -> ``PayslipParser.parse`` -> show the
suggestion -> the user confirms the amount -> ``periods.record_salary``.
A parser never books anything by itself.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class PayslipSuggestion:
    net_pay_cents: int
    pay_date: date | None
    employer: str | None
    confidence: float  # 0..1, shown to the user, never used to auto-confirm
    evidence: str  # the text line the amount was read from


class PayslipParser(Protocol):
    def parse(self, pdf: bytes) -> PayslipSuggestion | None: ...
