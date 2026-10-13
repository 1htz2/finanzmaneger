from enum import StrEnum


class PeriodStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class TransactionType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class IncomeKind(StrEnum):
    SALARY = "salary"
    OTHER = "other"


class Pot(StrEnum):
    """Places money can sit in. ``PERIOD`` means a spending bucket of the active period."""

    PERIOD = "period"
    RESERVE = "reserve"
    SAVINGS = "savings"


class CategoryKind(StrEnum):
    FIXED = "fixed"
    LEISURE = "leisure"
    INCOME = "income"


class AllocationSource(StrEnum):
    SALARY = "salary"
    SALARY_CORRECTION = "salary_correction"
    INCOME = "income"
    TRANSFER = "transfer"
    REVERSAL = "reversal"


class ReserveKind(StrEnum):
    PERIOD_CLOSE = "period_close"
    PERIOD_CORRECTION = "period_correction"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    INCOME = "income"
    TRANSFER = "transfer"
    REVERSAL = "reversal"


class SavingsKind(StrEnum):
    PERIOD_SAVINGS = "period_savings"
    SALARY_CORRECTION = "salary_correction"
    INCOME = "income"
    TRANSFER = "transfer"
    WITHDRAWAL = "withdrawal"
    REVERSAL = "reversal"


class CorrectionAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REVERSAL = "reversal"
    TRANSFER = "transfer"
