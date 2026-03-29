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
