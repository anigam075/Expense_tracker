from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExpenseRecord:
    id: int | None
    amount: float
    merchant: str
    payment_method: str
    expense_date: str
    notes: str
    source: str = "manual"


@dataclass(slots=True)
class NotificationReviewRecord:
    id: int | None
    source_app: str
    raw_text: str
    amount: float
    merchant: str
    payment_method: str
    expense_date: str
    notes: str
    status: str = "pending"


@dataclass(slots=True)
class StatementReviewRecord:
    id: int | None
    bank_name: str
    account_last4: str
    source_file: str
    amount: float
    direction: str
    merchant: str
    payment_method: str
    expense_date: str
    reference_no: str
    raw_row: str
    status: str = "pending"
