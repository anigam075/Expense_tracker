from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from pypdf import PdfReader


MONEY_RE = re.compile(r"\b\d[\d,]*\.\d{2}\b")
KOTAK_ROW_RE = re.compile(r"^\s*(\d+)\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})\s+(.*)")
ICICI_ROW_RE = re.compile(r"^\s*(\d{2}-\d{2}-\d{4})\s*(.*)")
IDFC_ROW_RE = re.compile(
    r"^\s*(\d{2}-[A-Za-z]{3}-\d{4})\s+(\d{2}-[A-Za-z]{3}-\d{4})\s+(.*)"
)
SBI_ROW_RE = re.compile(r"^\s*(\d{2}-\d{2}-\d{2})\s+(.*)")
SBI_TAIL_RE = re.compile(
    r"^(?P<description>.+?)\s+-\s+(?P<credit>\d[\d,]*(?:\.\d{1,2})?)\s+"
    r"(?P<debit>\d[\d,]*(?:\.\d{1,2})?)\s+(?P<balance>\d[\d,]*\.\d{2})$"
)


@dataclass(slots=True)
class ParsedStatementTransaction:
    bank_name: str
    account_last4: str
    txn_date: str
    value_date: str
    description: str
    reference_no: str
    merchant: str
    payment_method: str
    amount: float
    direction: str
    balance_after: float
    confidence: str
    raw_row: str


@dataclass(slots=True)
class ParseResult:
    bank_name: str
    account_last4: str
    transactions: list[ParsedStatementTransaction]
    warnings: list[str]


ProgressCallback = Callable[[str, int], None]


def parse_statement_pdf(pdf_path: str | Path, progress_callback: ProgressCallback | None = None) -> ParseResult:
    path = Path(pdf_path)
    _report_progress(progress_callback, "Opening statement PDF...", 5)
    text = extract_pdf_text(path, progress_callback=progress_callback)
    _report_progress(progress_callback, "Detecting bank format...", 35)
    bank = detect_bank(text)
    if bank == "kotak":
        return parse_kotak(text, progress_callback=progress_callback)
    if bank == "idfc":
        return parse_idfc(text, progress_callback=progress_callback)
    if bank == "icici":
        return parse_icici(text, progress_callback=progress_callback)
    if bank == "sbi":
        return parse_sbi(text, progress_callback=progress_callback)
    raise ValueError("Unsupported bank statement. Supported: Kotak, IDFC First, ICICI, SBI.")


def extract_pdf_text(path: Path, progress_callback: ProgressCallback | None = None) -> str:
    reader = PdfReader(str(path))
    texts: list[str] = []
    total_pages = max(len(reader.pages), 1)
    for index, page in enumerate(reader.pages, start=1):
        texts.append(page.extract_text() or "")
        percent = 5 + int((index / total_pages) * 25)
        _report_progress(progress_callback, f"Reading PDF page {index} of {total_pages}...", percent)
    return "\n".join(texts)


def detect_bank(text: str) -> str:
    upper = text.upper()
    if "IDFC FIRST BANK" in upper or "IDFB" in upper:
        return "idfc"
    if "STATE BANK OF INDIA" in upper or "SBIN" in upper or "TRANSACTION DETAILS" in upper:
        return "sbi"
    if "ICICI BANK" in upper or "ICICIBANK.COM" in upper:
        return "icici"
    if "KKBK" in upper or "KOTAK" in upper or "PAIDVIAKOTAKAPP" in upper:
        return "kotak"
    return "unknown"


def parse_kotak(text: str, progress_callback: ProgressCallback | None = None) -> ParseResult:
    account_last4 = _last4(_search_value(text, r"Account No\.\s*([0-9Xx*]+)"))
    lines = _clean_lines(text)
    rows = _group_rows(lines, KOTAK_ROW_RE, _is_kotak_noise)
    opening_balance = _extract_opening_balance(lines)
    previous_balance = opening_balance
    transactions: list[ParsedStatementTransaction] = []
    warnings: list[str] = []

    total_rows = max(len(rows), 1)
    for index, raw in enumerate(rows, start=1):
        match = KOTAK_ROW_RE.match(raw)
        if not match:
            continue
        _, date_text, body = match.groups()
        parsed = _parse_money_tail(body)
        if parsed is None:
            warnings.append(f"Could not parse amount/balance: {raw[:140]}")
            continue

        description, amount, balance_after = parsed
        direction, confidence = _direction_from_balance(previous_balance, balance_after)
        previous_balance = balance_after
        transactions.append(
            ParsedStatementTransaction(
                bank_name="Kotak Mahindra Bank",
                account_last4=account_last4,
                txn_date=_format_date(date_text, "%d %b %Y"),
                value_date="",
                description=description,
                reference_no=_extract_reference(description),
                merchant=_extract_merchant(description),
                payment_method=_infer_payment_method(description),
                amount=amount,
                direction=direction,
                balance_after=balance_after,
                confidence=confidence,
                raw_row=raw,
            )
        )
        if index == 1 or index == total_rows or index % 10 == 0:
            percent = 35 + int((index / total_rows) * 65)
            _report_progress(progress_callback, f"Parsing Kotak transactions ({index}/{total_rows})...", percent)

    _report_progress(progress_callback, "Finalizing parsed transactions...", 100)
    return ParseResult("Kotak Mahindra Bank", account_last4, transactions, warnings)


def parse_idfc(text: str, progress_callback: ProgressCallback | None = None) -> ParseResult:
    account_last4 = _last4(_search_value(text, r"ACCOUNT NO\s*:\s*([0-9Xx*]+)"))
    lines = _clean_lines(text)
    rows = _group_rows(lines, IDFC_ROW_RE, _is_idfc_noise)
    opening_balance = _extract_opening_balance(lines)
    previous_balance = opening_balance
    transactions: list[ParsedStatementTransaction] = []
    warnings: list[str] = []

    total_rows = max(len(rows), 1)
    for index, raw in enumerate(rows, start=1):
        match = IDFC_ROW_RE.match(raw)
        if not match:
            continue
        txn_date, value_date, body = match.groups()
        parsed = _parse_money_tail(body)
        if parsed is None:
            warnings.append(f"Could not parse amount/balance: {raw[:140]}")
            continue

        description, amount, balance_after = parsed
        direction, confidence = _direction_from_balance(previous_balance, balance_after)
        previous_balance = balance_after
        transactions.append(
            ParsedStatementTransaction(
                bank_name="IDFC First Bank",
                account_last4=account_last4,
                txn_date=_format_date(txn_date, "%d-%b-%Y"),
                value_date=_format_date(value_date, "%d-%b-%Y"),
                description=description,
                reference_no=_extract_reference(description),
                merchant=_extract_merchant(description),
                payment_method=_infer_payment_method(description),
                amount=amount,
                direction=direction,
                balance_after=balance_after,
                confidence=confidence,
                raw_row=raw,
            )
        )
        if index == 1 or index == total_rows or index % 10 == 0:
            percent = 35 + int((index / total_rows) * 65)
            _report_progress(progress_callback, f"Parsing IDFC transactions ({index}/{total_rows})...", percent)

    _report_progress(progress_callback, "Finalizing parsed transactions...", 100)
    return ParseResult("IDFC First Bank", account_last4, transactions, warnings)


def parse_icici(text: str, progress_callback: ProgressCallback | None = None) -> ParseResult:
    account_last4 = _last4(
        _search_value(text, r"Savings A/c\s+([Xx*0-9]+)")
        or _search_value(text, r"Savings Account\s+([Xx*0-9]+)")
    )
    transaction_text = _after_first_table_header(text)
    lines = _clean_lines(transaction_text)
    rows = _group_rows(lines, ICICI_ROW_RE, _is_icici_noise)
    previous_balance: float | None = None
    transactions: list[ParsedStatementTransaction] = []
    warnings: list[str] = []

    total_rows = max(len(rows), 1)
    for index, raw in enumerate(rows, start=1):
        match = ICICI_ROW_RE.match(raw)
        if not match:
            continue
        txn_date, body = match.groups()
        if re.search(r"\bB/F\b", body, flags=re.IGNORECASE):
            money = MONEY_RE.findall(body)
            if money:
                previous_balance = _to_money(money[-1])
            continue

        parsed = _parse_money_tail(body)
        if parsed is None:
            warnings.append(f"Could not parse amount/balance: {raw[:140]}")
            continue

        description, amount, balance_after = parsed
        direction, confidence = _direction_from_balance(previous_balance, balance_after)
        previous_balance = balance_after
        transactions.append(
            ParsedStatementTransaction(
                bank_name="ICICI Bank",
                account_last4=account_last4,
                txn_date=_format_date(txn_date, "%d-%m-%Y"),
                value_date="",
                description=description,
                reference_no=_extract_reference(description),
                merchant=_extract_merchant(description),
                payment_method=_infer_payment_method(description),
                amount=amount,
                direction=direction,
                balance_after=balance_after,
                confidence=confidence,
                raw_row=raw,
            )
        )
        if index == 1 or index == total_rows or index % 10 == 0:
            percent = 35 + int((index / total_rows) * 65)
            _report_progress(progress_callback, f"Parsing ICICI transactions ({index}/{total_rows})...", percent)

    _report_progress(progress_callback, "Finalizing parsed transactions...", 100)
    return ParseResult("ICICI Bank", account_last4, transactions, warnings)


def parse_sbi(text: str, progress_callback: ProgressCallback | None = None) -> ParseResult:
    account_last4 = _last4(_search_value(text, r"SAVING ACCOUNT\s+X+([0-9]+)"))
    transaction_text = _after_sbi_transaction_header(text)
    lines = _clean_lines(transaction_text)
    rows = _group_rows(lines, SBI_ROW_RE, _is_sbi_noise)
    transactions: list[ParsedStatementTransaction] = []
    warnings: list[str] = []

    total_rows = max(len(rows), 1)
    for index, raw in enumerate(rows, start=1):
        match = SBI_ROW_RE.match(raw)
        if not match:
            continue
        txn_date, body = match.groups()
        parsed = _parse_sbi_row(body)
        if parsed is None:
            warnings.append(f"Could not parse SBI row: {raw[:140]}")
            continue

        description, reference_no, credit, debit, balance_after = parsed
        if credit > 0 and debit == 0:
            direction = "credit"
            amount = credit
        elif debit > 0 and credit == 0:
            direction = "debit"
            amount = debit
        else:
            direction = "unknown"
            amount = debit or credit

        transactions.append(
            ParsedStatementTransaction(
                bank_name="State Bank of India",
                account_last4=account_last4,
                txn_date=_format_date(txn_date, "%d-%m-%y"),
                value_date="",
                description=description,
                reference_no=reference_no,
                merchant=_extract_merchant(description),
                payment_method=_infer_payment_method(description),
                amount=amount,
                direction=direction,
                balance_after=balance_after,
                confidence="high" if direction != "unknown" else "low",
                raw_row=raw,
            )
        )
        if index == 1 or index == total_rows or index % 10 == 0:
            percent = 35 + int((index / total_rows) * 65)
            _report_progress(progress_callback, f"Parsing SBI transactions ({index}/{total_rows})...", percent)

    _report_progress(progress_callback, "Finalizing parsed transactions...", 100)
    return ParseResult("State Bank of India", account_last4, transactions, warnings)


def _clean_lines(text: str) -> list[str]:
    cleaned = text.replace("\u00a0", " ")
    lines = []
    for line in cleaned.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return lines


def _group_rows(lines: Iterable[str], row_start_re: re.Pattern[str], is_noise) -> list[str]:
    rows: list[str] = []
    current: list[str] = []

    for line in lines:
        if is_noise(line):
            continue
        if row_start_re.match(line):
            if current:
                rows.append(" ".join(current))
            current = [line]
            continue
        if current:
            current.append(line)

    if current:
        rows.append(" ".join(current))
    return rows


def _parse_money_tail(body: str) -> tuple[str, float, float] | None:
    matches = list(MONEY_RE.finditer(body))
    if len(matches) < 2:
        return None

    amount_match = matches[-2]
    balance_match = matches[-1]
    description = body[: amount_match.start()].strip(" -")
    amount = _to_money(amount_match.group(0))
    balance_after = _to_money(balance_match.group(0))
    return description, amount, balance_after


def _parse_sbi_row(body: str) -> tuple[str, str, float, float, float] | None:
    match = SBI_TAIL_RE.match(body.strip())
    if not match:
        return None

    description_part = match.group("description").strip(" -")
    credit = _to_money(match.group("credit"))
    debit = _to_money(match.group("debit"))
    balance_after = _to_money(match.group("balance"))
    ref_match = re.search(r"\b\d{10,18}\b", description_part)
    reference_no = ref_match.group(0) if ref_match else ""
    return description_part, reference_no, credit, debit, balance_after


def _direction_from_balance(previous_balance: float | None, balance_after: float) -> tuple[str, str]:
    if previous_balance is None:
        return "unknown", "low"

    delta = round(balance_after - previous_balance, 2)
    if delta > 0:
        return "credit", "high"
    if delta < 0:
        return "debit", "high"
    return "unknown", "low"


def _extract_opening_balance(lines: Iterable[str]) -> float | None:
    for line in lines:
        if "Opening Balance" in line:
            money = MONEY_RE.findall(line)
            if money:
                return _to_money(money[-1])
    return None


def _after_first_table_header(text: str) -> str:
    marker = "DATE MODE PARTICULARS DEPOSITS WITHDRAWALS BALANCE"
    index = text.find(marker)
    if index == -1:
        return text
    return text[index + len(marker) :]


def _after_sbi_transaction_header(text: str) -> str:
    marker = "Date Transaction Reference Ref.No./Chq.No. Credit Debit Balance"
    index = text.find(marker)
    if index == -1:
        return text
    return text[index + len(marker) :]


def _is_kotak_noise(line: str) -> bool:
    return _matches_any(
        line,
        [
            r"^Savings Account Transactions$",
            r"^# Date Description",
            r"^Statement Generated",
            r"^Account Statement",
            r"^Account No\.",
            r"^ARPIT NIGAM$",
            r"^Page \d+",
        ],
    )


def _is_idfc_noise(line: str) -> bool:
    return _matches_any(
        line,
        [
            r"^STATEMENT OF ACCOUNT$",
            r"^Transaction$",
            r"^Date$",
            r"^Value Date",
            r"^No$",
            r"^Debit Credit Balance$",
            r"^REGISTERED OFFICE:",
            r"^Page \d+",
            r"^Opening Balance Total Debit",
            r"^\d[\d,]*\.\d{2}\s+\d[\d,]*\.\d{2}\s+\d[\d,]*\.\d{2}\s+\d[\d,]*\.\d{2}$",
        ],
    )


def _is_icici_noise(line: str) -> bool:
    return _matches_any(
        line,
        [
            r"^Statement of Transactions",
            r"^DATE MODE PARTICULARS",
            r"^Total:",
            r"^Page \d+",
            r"^Never share",
            r"^Ã…",
        ],
    )


def _is_sbi_noise(line: str) -> bool:
    return _matches_any(
        line,
        [
            r"^null null null null null null$",
            r"^TRANSACTION OVERVIEW$",
            r"^Your Opening Balance",
            r"^Your Closing Balance",
            r"^\*All dates are in",
            r"^Visit https://sbi\.co\.in",
            r"^\d+ of \d+Number",
            r"^Balance$",
            r"^Transaction$",
            r"^Accounts$",
            r"^Details$",
            r"^Summary$",
            r"^Welcome ",
            r"^As on ",
        ],
    )


def _matches_any(line: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns)


def _extract_reference(description: str) -> str:
    patterns = [
        r"\bUPI-\d+\b",
        r"\b(?:IBL|PTM|AIR|ESBZ|PYTM|APY|Gtxn|KJP)[A-Za-z0-9]+\b",
        r"\b\d{10,18}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(0)
    return ""


def _extract_merchant(description: str) -> str:
    compact = " ".join(description.split())
    parts = compact.split("/")
    if parts and parts[0].upper() == "UPI" and len(parts) > 1:
        return _clean_merchant(parts[1])
    if compact.upper().startswith("UPI/DR/") or compact.upper().startswith("UPI/CR/"):
        if len(parts) > 3:
            return _clean_merchant(parts[3])
    if parts and parts[0].upper() == "ACH" and len(parts) > 1:
        return _clean_merchant(parts[1])
    if compact.upper().startswith("ACHCR "):
        tokens = compact.split()
        return _clean_merchant(" ".join(tokens[2:])) if len(tokens) > 2 else "ACH Credit"
    if compact.upper().startswith("OTHER ATMS"):
        return "ATM Cash Withdrawal"
    if "MONTHLY SAVINGS INTEREST" in compact.upper() or compact.upper().startswith("INTEREST CREDIT"):
        return "Savings Interest"
    if "SALARY" in compact.upper():
        return "Salary"
    if compact.upper().startswith("NEFT") or compact.upper().startswith("NEFT*"):
        return _clean_merchant(compact.replace("NEFT*", "", 1).replace("NEFT", "", 1))
    return _clean_merchant(compact[:60])


def _clean_merchant(value: str) -> str:
    value = re.sub(r"[@/].*", "", value)
    value = re.sub(r"\b\d{6,}\b", "", value)
    value = re.sub(r"[*]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_.")
    if not value:
        return "Unknown"
    return value.title()


def _search_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _last4(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-4:] if digits else ""


def _format_date(value: str, fmt: str) -> str:
    try:
        return datetime.strptime(value.strip(), fmt).date().isoformat()
    except ValueError:
        return value.strip()


def _to_money(value: str) -> float:
    return float(value.replace(",", ""))


def _infer_payment_method(description: str) -> str:
    upper = description.upper()
    if upper.startswith("UPI/"):
        return "UPI"
    if upper.startswith("ACH") or "ACH/" in upper:
        return "ACH"
    if upper.startswith("NEFT") or "NEFT*" in upper:
        return "NEFT"
    if upper.startswith("IMPS"):
        return "IMPS"
    if "ATM" in upper or "CASH WDL" in upper:
        return "Cash"
    if upper.startswith("BIL/"):
        return "Card"
    return "Bank Transfer"


def _report_progress(progress_callback: ProgressCallback | None, message: str, percent: int) -> None:
    if progress_callback is None:
        return
    progress_callback(message, max(0, min(percent, 100)))
