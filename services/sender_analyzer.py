"""Sender analysis: who does the message *say* it is from, and does that add up?

Observations are deliberately worded as things to verify, never as proof.
"""
import re

from .brands import brands_mentioned, is_official_domain

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "outlook.com", "hotmail.com",
    "live.com", "rediffmail.com", "protonmail.com", "proton.me", "aol.com", "icloud.com",
    "zoho.com", "gmx.com", "mail.com", "yandex.com",
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
UPI_RE = re.compile(r"\b[A-Za-z0-9._-]{2,}@(?:ybl|ibl|axl|paytm|okaxis|oksbi|okhdfcbank|okicici|upi|apl|ptyes|ptsbi|axisbank|icici|sbi|hdfcbank)\b", re.I)
PHONE_RE = re.compile(r"(?<![\w+])(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,6}(?!\w)")
SENDER_ID_RE = re.compile(r"\b[A-Z]{2}-[A-Z0-9]{5,6}(?:-[A-Z])?\b")
FROM_RE = re.compile(r"^\s*(?:from|sender)\s*:\s*(.+)$", re.I | re.M)
NAME_EMAIL_RE = re.compile(r"^\s*\"?([^<\"]+?)\"?\s*<([^>]+)>")


def _classify_phone(raw: str):
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8:
        return None
    if raw.strip().startswith("+") and not raw.strip().startswith("+91"):
        return {"number": raw.strip(), "format": "International (non-Indian) number"}
    local = digits[2:] if digits.startswith("91") and len(digits) == 12 else digits
    if len(local) == 10 and local[0] in "6789":
        return {"number": raw.strip(), "format": "Indian mobile number"}
    if local.startswith("1800") or local.startswith("1860"):
        return {"number": raw.strip(), "format": "Indian toll-free number"}
    return {"number": raw.strip(), "format": "Other / landline format"}


def analyze_sender(text: str) -> dict:
    text = text or ""
    sender_name = None
    from_line = FROM_RE.search(text)
    if from_line:
        m = NAME_EMAIL_RE.match(from_line.group(1))
        sender_name = (m.group(1) if m else from_line.group(1)).strip()

    upi_ids = sorted({u for u in UPI_RE.findall(text)})
    emails = []
    for addr in dict.fromkeys(EMAIL_RE.findall(text)):
        if addr in upi_ids:
            continue
        domain = addr.split("@", 1)[1].lower()
        emails.append({"address": addr, "domain": domain, "free_provider": domain in FREE_EMAIL_PROVIDERS})

    phones = []
    for raw in dict.fromkeys(PHONE_RE.findall(text)):
        info = _classify_phone(raw)
        if info:
            phones.append(info)

    sender_ids = sorted(set(SENDER_ID_RE.findall(text)))
    claimed = brands_mentioned(text)

    observations = []
    for brand in claimed:
        for e in emails:
            if e["free_provider"]:
                observations.append({
                    "level": "warn",
                    "text": f"The message mentions {brand['name']}, but the email address uses a free provider "
                            f"({e['domain']}). Organisations usually write from their own domain.",
                })
            elif not is_official_domain(brand, e["domain"]):
                observations.append({
                    "level": "warn",
                    "text": f"The claimed identity ({brand['name']}) and the email domain ({e['domain']}) may not match.",
                })
        for p in phones:
            if p["format"] == "Indian mobile number":
                observations.append({
                    "level": "info",
                    "text": f"A personal mobile number is given as a contact for {brand['name']}. "
                            "Check the official website for the organisation's real support number.",
                })
            elif p["format"].startswith("International"):
                observations.append({
                    "level": "warn",
                    "text": f"An international number ({p['number']}) is given for {brand['name']}. Verify before calling or replying.",
                })

    if upi_ids:
        observations.append({
            "level": "warn",
            "text": "A UPI ID is included for sending money (" + ", ".join(upi_ids) + "). "
                    "Payment requests should be verified through a channel you already trust.",
        })
    if sender_ids:
        observations.append({
            "level": "info",
            "text": "SMS header(s) " + ", ".join(sender_ids) + " found. Registered headers are a good sign, "
                    "but compare them with headers you have received from the organisation before.",
        })

    # de-duplicate while preserving order
    seen, unique = set(), []
    for o in observations:
        if o["text"] not in seen:
            seen.add(o["text"])
            unique.append(o)

    present = bool(sender_name or emails or phones or sender_ids or upi_ids or claimed)
    return {
        "present": present,
        "sender_name": sender_name,
        "emails": emails,
        "phones": phones,
        "sender_ids": sender_ids,
        "upi_ids": upi_ids,
        "claimed_organizations": [b["name"] for b in claimed],
        "observations": unique,
    }
