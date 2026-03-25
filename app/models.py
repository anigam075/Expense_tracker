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
