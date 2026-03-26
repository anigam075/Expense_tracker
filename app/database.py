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

    def update_expense(self, expense: ExpenseRecord) -> ExpenseRecord:
        if expense.id is None:
            raise ValueError("Expense id is required for updates.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE expenses
                SET amount = ?,
                    merchant = ?,
                    payment_method = ?,
                    expense_date = ?,
                    notes = ?,
                    source = ?
                WHERE id = ?
                """,
                (
                    expense.amount,
                    expense.merchant,
                    expense.payment_method,
                    expense.expense_date,
                    expense.notes,
                    expense.source,
                    expense.id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Expense with id {expense.id} was not found.")

        return expense

    def get_expense(self, expense_id: int) -> ExpenseRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, amount, merchant, payment_method, expense_date, notes, source
                FROM expenses
                WHERE id = ?
                """,
                (expense_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def delete_expense(self, expense_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM expenses
                WHERE id = ?
                """,
                (expense_id,),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Expense with id {expense_id} was not found.")

    def list_expenses(self, limit: int = 100) -> list[ExpenseRecord]:
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

        return [self._row_to_record(row) for row in rows]

    def list_recent_expenses(self, limit: int = 10) -> list[ExpenseRecord]:
        return self.list_expenses(limit=limit)

    def _row_to_record(self, row: sqlite3.Row) -> ExpenseRecord:
        return ExpenseRecord(
            id=row["id"],
            amount=row["amount"],
            merchant=row["merchant"],
            payment_method=row["payment_method"],
            expense_date=row["expense_date"],
            notes=row["notes"],
            source=row["source"],
        )
