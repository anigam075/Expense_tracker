from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class ParsedNotification:
    source_app: str
    amount: float
    merchant: str
    payment_method: str
    expense_date: str
    notes: str
    raw_text: str


AMOUNT_PATTERNS = [
    re.compile(r"(?:rs\.?|inr)\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.IGNORECASE),
    re.compile(r"([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:rs\.?|inr)", re.IGNORECASE),
]

MERCHANT_PATTERNS = [
    re.compile(r"(?:paid to|sent to|payment to|debited for|spent at|credited to)\s+([a-z0-9 .&_-]+)", re.IGNORECASE),
    re.compile(r"\bto\s+([a-z0-9 .&_-]+)", re.IGNORECASE),
    re.compile(r"\bat\s+([a-z0-9 .&_-]+)", re.IGNORECASE),
]


def parse_notification_text(raw_text: str, source_app: str = "Notification") -> ParsedNotification | None:
    normalized = " ".join(raw_text.split()).strip()
    if not normalized:
        return None

    amount = _extract_amount(normalized)
    if amount is None:
        return None

    merchant = _extract_merchant(normalized)
    return ParsedNotification(
        source_app=source_app.strip() or "Notification",
        amount=amount,
        merchant=merchant or "Unknown Merchant",
        payment_method="UPI" if _looks_like_upi(normalized) else "Card",
        expense_date=date.today().isoformat(),
        notes=normalized,
        raw_text=normalized,
    )


def _extract_amount(text: str) -> float | None:
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", "")
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _extract_merchant(text: str) -> str:
    for pattern in MERCHANT_PATTERNS:
        match = pattern.search(text)
        if match:
            merchant = match.group(1).strip(" .,-")
            merchant = merchant.split(" on ")[0].split(" via ")[0]
            if merchant:
                return merchant.title()
    return ""


def _looks_like_upi(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("upi", "gpay", "google pay", "phonepe", "paytm"))
