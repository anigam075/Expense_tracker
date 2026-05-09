from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models import ExpenseRecord, NotificationReviewRecord, StatementReviewRecord


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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_app TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    amount REAL NOT NULL,
                    merchant TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS statement_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_name TEXT NOT NULL,
                    account_last4 TEXT NOT NULL DEFAULT '',
                    source_file TEXT NOT NULL DEFAULT '',
                    amount REAL NOT NULL,
                    direction TEXT NOT NULL DEFAULT 'unknown',
                    merchant TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    reference_no TEXT NOT NULL DEFAULT '',
                    raw_row TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
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

    def list_expenses(self, limit: int | None = 100) -> list[ExpenseRecord]:
        with self._connect() as connection:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT id, amount, merchant, payment_method, expense_date, notes, source
                    FROM expenses
                    ORDER BY expense_date DESC, id DESC
                    """
                ).fetchall()
            else:
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

    def add_notification_review(self, review: NotificationReviewRecord) -> NotificationReviewRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO notification_reviews (
                    source_app,
                    raw_text,
                    amount,
                    merchant,
                    payment_method,
                    expense_date,
                    notes,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.source_app,
                    review.raw_text,
                    review.amount,
                    review.merchant,
                    review.payment_method,
                    review.expense_date,
                    review.notes,
                    review.status,
                ),
            )

        return NotificationReviewRecord(
            id=cursor.lastrowid,
            source_app=review.source_app,
            raw_text=review.raw_text,
            amount=review.amount,
            merchant=review.merchant,
            payment_method=review.payment_method,
            expense_date=review.expense_date,
            notes=review.notes,
            status=review.status,
        )

    def list_notification_reviews(self, status: str = "pending") -> list[NotificationReviewRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, source_app, raw_text, amount, merchant, payment_method, expense_date, notes, status
                FROM notification_reviews
                WHERE status = ?
                ORDER BY id DESC
                """,
                (status,),
            ).fetchall()

        return [self._row_to_notification_review(row) for row in rows]

    def get_notification_review(self, review_id: int) -> NotificationReviewRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, source_app, raw_text, amount, merchant, payment_method, expense_date, notes, status
                FROM notification_reviews
                WHERE id = ?
                """,
                (review_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_notification_review(row)

    def update_notification_review(self, review: NotificationReviewRecord) -> NotificationReviewRecord:
        if review.id is None:
            raise ValueError("Notification review id is required for updates.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE notification_reviews
                SET source_app = ?,
                    raw_text = ?,
                    amount = ?,
                    merchant = ?,
                    payment_method = ?,
                    expense_date = ?,
                    notes = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    review.source_app,
                    review.raw_text,
                    review.amount,
                    review.merchant,
                    review.payment_method,
                    review.expense_date,
                    review.notes,
                    review.status,
                    review.id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Notification review with id {review.id} was not found.")

        return review

    def confirm_notification_review(self, review: NotificationReviewRecord) -> ExpenseRecord:
        updated_review = self.update_notification_review(
            NotificationReviewRecord(
                id=review.id,
                source_app=review.source_app,
                raw_text=review.raw_text,
                amount=review.amount,
                merchant=review.merchant,
                payment_method=review.payment_method,
                expense_date=review.expense_date,
                notes=review.notes,
                status="confirmed",
            )
        )
        return self.add_expense(
            ExpenseRecord(
                id=None,
                amount=updated_review.amount,
                merchant=updated_review.merchant,
                payment_method=updated_review.payment_method,
                expense_date=updated_review.expense_date,
                notes=updated_review.notes,
                source="notification",
            )
        )

    def reject_notification_review(self, review_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE notification_reviews
                SET status = 'rejected'
                WHERE id = ?
                """,
                (review_id,),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Notification review with id {review_id} was not found.")

    def get_state(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_state (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def add_statement_review(self, review: StatementReviewRecord) -> StatementReviewRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO statement_reviews (
                    bank_name,
                    account_last4,
                    source_file,
                    amount,
                    direction,
                    merchant,
                    payment_method,
                    expense_date,
                    reference_no,
                    raw_row,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.bank_name,
                    review.account_last4,
                    review.source_file,
                    review.amount,
                    review.direction,
                    review.merchant,
                    review.payment_method,
                    review.expense_date,
                    review.reference_no,
                    review.raw_row,
                    review.status,
                ),
            )

        return StatementReviewRecord(
            id=cursor.lastrowid,
            bank_name=review.bank_name,
            account_last4=review.account_last4,
            source_file=review.source_file,
            amount=review.amount,
            direction=review.direction,
            merchant=review.merchant,
            payment_method=review.payment_method,
            expense_date=review.expense_date,
            reference_no=review.reference_no,
            raw_row=review.raw_row,
            status=review.status,
        )

    def list_statement_reviews(self, status: str = "pending") -> list[StatementReviewRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, bank_name, account_last4, source_file, amount, direction, merchant,
                       payment_method, expense_date, reference_no, raw_row, status
                FROM statement_reviews
                WHERE status = ?
                ORDER BY expense_date DESC, id DESC
                """,
                (status,),
            ).fetchall()

        return [self._row_to_statement_review(row) for row in rows]

    def get_statement_review(self, review_id: int) -> StatementReviewRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, bank_name, account_last4, source_file, amount, direction, merchant,
                       payment_method, expense_date, reference_no, raw_row, status
                FROM statement_reviews
                WHERE id = ?
                """,
                (review_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_statement_review(row)

    def update_statement_review(self, review: StatementReviewRecord) -> StatementReviewRecord:
        if review.id is None:
            raise ValueError("Statement review id is required for updates.")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE statement_reviews
                SET bank_name = ?,
                    account_last4 = ?,
                    source_file = ?,
                    amount = ?,
                    direction = ?,
                    merchant = ?,
                    payment_method = ?,
                    expense_date = ?,
                    reference_no = ?,
                    raw_row = ?,
                    status = ?
                WHERE id = ?
                """,
                (
                    review.bank_name,
                    review.account_last4,
                    review.source_file,
                    review.amount,
                    review.direction,
                    review.merchant,
                    review.payment_method,
                    review.expense_date,
                    review.reference_no,
                    review.raw_row,
                    review.status,
                    review.id,
                ),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Statement review with id {review.id} was not found.")

        return review

    def confirm_statement_review(self, review: StatementReviewRecord) -> ExpenseRecord:
        updated_review = self.update_statement_review(
            StatementReviewRecord(
                id=review.id,
                bank_name=review.bank_name,
                account_last4=review.account_last4,
                source_file=review.source_file,
                amount=review.amount,
                direction=review.direction,
                merchant=review.merchant,
                payment_method=review.payment_method,
                expense_date=review.expense_date,
                reference_no=review.reference_no,
                raw_row=review.raw_row,
                status="confirmed",
            )
        )
        return self.add_expense(
            ExpenseRecord(
                id=None,
                amount=updated_review.amount,
                merchant=updated_review.merchant,
                payment_method=updated_review.payment_method,
                expense_date=updated_review.expense_date,
                notes=f"{updated_review.bank_name} x{updated_review.account_last4}".strip(),
                source="statement",
            )
        )

    def reject_statement_review(self, review_id: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE statement_reviews
                SET status = 'rejected'
                WHERE id = ?
                """,
                (review_id,),
            )

        if cursor.rowcount == 0:
            raise ValueError(f"Statement review with id {review_id} was not found.")

    def clear_statement_reviews(self, status: str = "pending") -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM statement_reviews
                WHERE status = ?
                """,
                (status,),
            )
        return int(cursor.rowcount)

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

    def _row_to_notification_review(self, row: sqlite3.Row) -> NotificationReviewRecord:
        return NotificationReviewRecord(
            id=row["id"],
            source_app=row["source_app"],
            raw_text=row["raw_text"],
            amount=row["amount"],
            merchant=row["merchant"],
            payment_method=row["payment_method"],
            expense_date=row["expense_date"],
            notes=row["notes"],
            status=row["status"],
        )

    def _row_to_statement_review(self, row: sqlite3.Row) -> StatementReviewRecord:
        return StatementReviewRecord(
            id=row["id"],
            bank_name=row["bank_name"],
            account_last4=row["account_last4"],
            source_file=row["source_file"],
            amount=row["amount"],
            direction=row["direction"],
            merchant=row["merchant"],
            payment_method=row["payment_method"],
            expense_date=row["expense_date"],
            reference_no=row["reference_no"],
            raw_row=row["raw_row"],
            status=row["status"],
        )
