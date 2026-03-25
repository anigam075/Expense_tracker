from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import ExpenseRecord


class ExpenseRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    merchant TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add_expense(self, expense: ExpenseRecord) -> ExpenseRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO expenses (
                    amount,
                    merchant,
                    payment_method,
                    expense_date,
                    notes,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    expense.amount,
                    expense.merchant,
                    expense.payment_method,
                    expense.expense_date,
                    expense.notes,
                    expense.source,
                ),
            )

        return ExpenseRecord(
            id=cursor.lastrowid,
            amount=expense.amount,
            merchant=expense.merchant,
            payment_method=expense.payment_method,
            expense_date=expense.expense_date,
            notes=expense.notes,
            source=expense.source,
        )

    def list_recent_expenses(self, limit: int = 10) -> list[ExpenseRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, amount, merchant, payment_method, expense_date, notes, source
                FROM expenses
                ORDER BY expense_date DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            ExpenseRecord(
                id=row["id"],
                amount=row["amount"],
                merchant=row["merchant"],
                payment_method=row["payment_method"],
                expense_date=row["expense_date"],
                notes=row["notes"],
                source=row["source"],
            )
            for row in rows
        ]
