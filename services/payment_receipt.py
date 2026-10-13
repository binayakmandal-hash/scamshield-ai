"""Golden hour: pull the details a fraud complaint needs out of a payment screenshot or bank SMS.

After a UPI fraud, the 1930 helpline and cybercrime.gov.in ask for the amount, the date and time, the
UTR (UPI reference number) and who the money went to. Finding these in a panic is hard, so we read them
from the receipt the person already has. Every field is optional and editable in the UI: a field we can't
find stays empty rather than guessed.
"""
from __future__ import annotations

import re

from .upi_check import AMOUNT_RE, EMAIL_TLDS, VPA_RE

UTR_RE = re.compile(
    r"(?:utr|upi ?(?:ref(?:erence)?|txn|transaction)(?: ?(?:no|number|id))?|rrn|ref(?:erence)?\.? ?(?:no|number)?|bank reference)"
    r"[\s.:#-]*(\d{12})\b", re.I)
TXN_RE = re.compile(r"(?:transaction|txn|order)\s?(?:id|no\.?|number)[\s.:#-]*([A-Z0-9]{10,35})\b", re.I)
BARE_12 = re.compile(r"(?<!\d)(\d{12})(?!\d)")
DATE_RE = re.compile(
    r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}[ -](?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[ ,-]+\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]* \d{1,2},? \d{4})\b", re.I)
TIME_RE = re.compile(r"\b(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?\s?(?:[ap]\.?m\.?)?)", re.I)
PAYEE_RE = re.compile(
    r"(?:paid to|sent to|payment to|money sent to|transferred to|to:|to\s+(?=[A-Z]))\s*([A-Z][A-Za-z.&' ]{1,40}?)(?=\s*(?:\n|$|\d|₹|rs|upi|[A-Za-z0-9._-]+@|banking|on |at |a/c))",
    re.I | re.M)
DEBIT_RE = re.compile(r"\b(debited|paid|sent|transferred|deducted|payment (?:successful|completed)|withdrawn)\b", re.I)
APP_HINTS = [("Google Pay", r"google ?pay|\bg ?pay\b"), ("PhonePe", r"phone ?pe"), ("Paytm", r"paytm"),
             ("BHIM", r"\bbhim\b"), ("Amazon Pay", r"amazon ?pay"), ("CRED", r"\bcred\b"), ("WhatsApp Pay", r"whatsapp")]
BANK_HINTS = ["SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "Bank of Baroda", "Canara", "Union Bank", "IDFC", "Yes Bank",
              "IndusInd", "Bank of India", "Indian Bank", "UCO"]


def extract(text: str) -> dict:
    """Return {fields, found, debit_seen}. Fields: amount, date, time, utr, txn_id, payee_name, payee_vpa, app, bank."""
    text = (text or "").replace("\r", "")
    flat = re.sub(r"[ \t]+", " ", text)
    fields: dict[str, str | None] = dict.fromkeys(
        ("amount", "date", "time", "utr", "txn_id", "payee_name", "payee_vpa", "app", "bank"))

    m = AMOUNT_RE.search(flat)
    if m:
        fields["amount"] = m.group(1).replace(",", "")
    else:  # GPay-style big number on its own line: "₹" sometimes OCRs as "%" or "2"
        m = re.search(r"^\s*[%₹z2]?\s?(\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?)\s*$", text, re.M)
        if m and DEBIT_RE.search(flat):
            fields["amount"] = m.group(1).replace(",", "")

    m = UTR_RE.search(flat)
    if m:
        fields["utr"] = m.group(1)
    else:
        bare = BARE_12.findall(flat)
        if len(bare) == 1:
            fields["utr"] = bare[0]
    m = TXN_RE.search(flat)
    if m and m.group(1) != fields["utr"]:
        fields["txn_id"] = m.group(1)

    m = DATE_RE.search(flat)
    if m:
        fields["date"] = m.group(1)
    for m in TIME_RE.finditer(flat):
        candidate = m.group(1)
        if fields["date"] and candidate in fields["date"]:
            continue
        fields["time"] = candidate.strip()
        break

    vpa = next((v for v in VPA_RE.finditer(flat) if not EMAIL_TLDS.match(v.group(2)) and "." not in v.group(2)), None)
    if vpa:
        fields["payee_vpa"] = vpa.group(0)
    m = PAYEE_RE.search(text)
    if m:
        name = m.group(1).strip(" .")
        if name.lower() not in {"you", "your", "your account", "a/c", "account", "vpa", "upi", "upi id", "beneficiary"}:
            fields["payee_name"] = name

    low = flat.lower()
    fields["app"] = next((name for name, pat in APP_HINTS if re.search(pat, low)), None)
    fields["bank"] = next((b for b in BANK_HINTS if re.search(r"\b" + re.escape(b.lower()) + r"\b", low)), None)

    return {"fields": fields, "found": sorted(k for k, v in fields.items() if v), "debit_seen": bool(DEBIT_RE.search(flat))}
