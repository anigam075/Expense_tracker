from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.models import ExpenseRecord

CSV_HEADERS = ["amount", "merchant", "payment_method", "expense_date", "notes", "source", "status"]
REQUIRED_HEADERS = {"amount", "merchant", "payment_method", "expense_date"}


@dataclass(slots=True)
class CsvImportIssue:
    row_number: int
    message: str


@dataclass(slots=True)
class CsvImportResult:
    total_rows: int
    importable_rows: list[ExpenseRecord] = field(default_factory=list)
    duplicate_rows: list[ExpenseRecord] = field(default_factory=list)
    invalid_rows: list[CsvImportIssue] = field(default_factory=list)
    missing_headers: list[str] = field(default_factory=list)


def build_transactions_csv(expenses: list[ExpenseRecord]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS)
    writer.writeheader()
    for expense in expenses:
        writer.writerow(
            {
                "amount": f"{expense.amount:.2f}",
                "merchant": expense.merchant,
                "payment_method": expense.payment_method,
                "expense_date": expense.expense_date,
                "notes": expense.notes,
                "source": expense.source or "manual",
                "status": "confirmed",
            }
        )
    return buffer.getvalue()


def export_transactions_csv(expenses: list[ExpenseRecord], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_transactions_csv(expenses), encoding="utf-8", newline="")
    return output


def parse_transactions_csv(csv_path: str | Path, existing_expenses: list[ExpenseRecord]) -> CsvImportResult:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = [header.strip() for header in reader.fieldnames or []]
        missing_headers = sorted(REQUIRED_HEADERS.difference(headers))
        if missing_headers:
            return CsvImportResult(total_rows=0, missing_headers=missing_headers)

        existing_keys = {_expense_key(expense) for expense in existing_expenses}
        seen_import_keys: set[tuple[float, str, str, str]] = set()
        result = CsvImportResult(total_rows=0)

        for row_number, raw_row in enumerate(reader, start=2):
            result.total_rows += 1
            row = {str(key).strip(): _normalize_text(value) for key, value in raw_row.items() if key is not None}
            parsed = _parse_row(row, row_number)
            if isinstance(parsed, CsvImportIssue):
                result.invalid_rows.append(parsed)
                continue

            key = _expense_key(parsed)
            if key in existing_keys or key in seen_import_keys:
                result.duplicate_rows.append(parsed)
                continue

            seen_import_keys.add(key)
            result.importable_rows.append(parsed)

        return result


def _parse_row(row: dict[str, str], row_number: int) -> ExpenseRecord | CsvImportIssue:
    amount_text = row.get("amount", "")
    merchant = row.get("merchant", "")
    payment_method = row.get("payment_method", "")
    expense_date = row.get("expense_date", "")
    notes = row.get("notes", "")
    source = row.get("source", "") or "manual"
    status = (row.get("status", "") or "confirmed").lower()

    if status not in {"confirmed", ""}:
        return CsvImportIssue(row_number=row_number, message="Only confirmed transaction rows can be imported.")

    if not amount_text or not merchant or not payment_method or not expense_date:
        return CsvImportIssue(
            row_number=row_number,
            message="Amount, merchant, payment method, and expense date are required.",
        )

    try:
        amount = float(amount_text)
    except ValueError:
        return CsvImportIssue(row_number=row_number, message="Amount must be numeric.")

    if amount <= 0:
        return CsvImportIssue(row_number=row_number, message="Amount must be greater than zero.")

    try:
        date.fromisoformat(expense_date)
    except ValueError:
        return CsvImportIssue(row_number=row_number, message="Expense date must use YYYY-MM-DD.")

    return ExpenseRecord(
        id=None,
        amount=amount,
        merchant=merchant,
        payment_method=payment_method,
        expense_date=expense_date,
        notes=notes,
        source=source,
    )


def _expense_key(expense: ExpenseRecord) -> tuple[float, str, str, str]:
    return (
        round(float(expense.amount), 2),
        expense.expense_date,
        expense.merchant.strip().lower(),
        expense.payment_method.strip().lower(),
    )


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())
