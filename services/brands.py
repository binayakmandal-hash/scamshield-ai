"""Organisations that scammers commonly imitate, with their official domains.

Used for two checks:
  * does a URL *mention* a brand without being on one of its official domains?
  * does a sender *claim* to be a brand but write from a different domain?

Extend this list freely - it is plain data.
"""
import re

BRANDS = [
    {"name": "SBI", "keywords": ["sbi", "state bank of india", "yono"], "tokens": ["sbi", "onlinesbi", "yono"],
     "domains": ["sbi.co.in", "onlinesbi.sbi", "sbi.bank.in", "onlinesbi.com", "sbi"]},
    {"name": "HDFC Bank", "keywords": ["hdfc"], "tokens": ["hdfc", "hdfcbank"], "domains": ["hdfcbank.com", "hdfc.bank.in", "hdfc.com"]},
    {"name": "ICICI Bank", "keywords": ["icici"], "tokens": ["icici", "icicibank"], "domains": ["icicibank.com", "icici.bank.in"]},
    {"name": "Axis Bank", "keywords": ["axis bank"], "tokens": ["axisbank"], "domains": ["axisbank.com", "axis.bank.in"]},
    {"name": "Kotak Mahindra Bank", "keywords": ["kotak"], "tokens": ["kotak"], "domains": ["kotak.com"]},
    {"name": "Reserve Bank of India", "keywords": ["rbi", "reserve bank"], "tokens": ["rbi"], "domains": ["rbi.org.in"]},
    {"name": "Paytm", "keywords": ["paytm"], "tokens": ["paytm"], "domains": ["paytm.com", "paytm.in"]},
    {"name": "PhonePe", "keywords": ["phonepe"], "tokens": ["phonepe"], "domains": ["phonepe.com"]},
    {"name": "Google Pay", "keywords": ["google pay", "gpay"], "tokens": ["gpay", "googlepay"], "domains": ["google.com"]},
    {"name": "Amazon", "keywords": ["amazon"], "tokens": ["amazon"], "domains": ["amazon.in", "amazon.com", "amazon.jobs"]},
    {"name": "Flipkart", "keywords": ["flipkart"], "tokens": ["flipkart"], "domains": ["flipkart.com"]},
    {"name": "India Post", "keywords": ["india post", "indiapost"], "tokens": ["indiapost", "indpost"], "domains": ["indiapost.gov.in"]},
    {"name": "Income Tax Department", "keywords": ["income tax", "incometax"], "tokens": ["incometax"], "domains": ["incometax.gov.in"]},
    {"name": "UIDAI (Aadhaar)", "keywords": ["uidai"], "tokens": ["uidai", "aadhaar", "aadhar"], "domains": ["uidai.gov.in"]},
    {"name": "National Scholarship Portal", "keywords": ["national scholarship portal", "nsp"], "tokens": ["nsp", "scholarship"],
     "domains": ["scholarships.gov.in"]},
    {"name": "KBC", "keywords": ["kbc", "kaun banega crorepati"], "tokens": ["kbc"], "domains": ["sonyliv.com", "setindia.com"]},
    {"name": "Microsoft", "keywords": ["microsoft"], "tokens": ["microsoft", "office365", "outlook"],
     "domains": ["microsoft.com", "live.com", "outlook.com", "office.com"]},
    {"name": "Google", "keywords": ["google"], "tokens": ["google", "gmail"], "domains": ["google.com", "gmail.com", "google.co.in"]},
    {"name": "Apple", "keywords": ["apple id", "icloud"], "tokens": ["apple", "icloud"], "domains": ["apple.com", "icloud.com"]},
    {"name": "PayPal", "keywords": ["paypal"], "tokens": ["paypal"], "domains": ["paypal.com"]},
    {"name": "Netflix", "keywords": ["netflix"], "tokens": ["netflix"], "domains": ["netflix.com"]},
    {"name": "WhatsApp", "keywords": [], "tokens": ["whatsapp"], "domains": ["whatsapp.com", "wa.me"]},
    {"name": "Airtel", "keywords": ["airtel"], "tokens": ["airtel"], "domains": ["airtel.in", "airtel.com"]},
    {"name": "Jio", "keywords": ["jio"], "tokens": ["jio"], "domains": ["jio.com"]},
    {"name": "DHL", "keywords": ["dhl"], "tokens": ["dhl"], "domains": ["dhl.com"]},
    {"name": "FedEx", "keywords": ["fedex"], "tokens": ["fedex"], "domains": ["fedex.com"]},
    {"name": "Blue Dart", "keywords": ["blue dart", "bluedart"], "tokens": ["bluedart"], "domains": ["bluedart.com"]},
    {"name": "TCS", "keywords": ["tcs", "tata consultancy"], "tokens": ["tcs"], "domains": ["tcs.com"]},
    {"name": "Infosys", "keywords": ["infosys"], "tokens": ["infosys"], "domains": ["infosys.com"]},
    {"name": "Wipro", "keywords": ["wipro"], "tokens": ["wipro"], "domains": ["wipro.com"]},
    {"name": "LinkedIn", "keywords": ["linkedin"], "tokens": ["linkedin"], "domains": ["linkedin.com"]},
    {"name": "Naukri", "keywords": ["naukri"], "tokens": ["naukri"], "domains": ["naukri.com"]},
]

_KEYWORD_PATTERNS = [
    (b, re.compile(r"\b(?:" + "|".join(re.escape(k) for k in b["keywords"]) + r")\b", re.I))
    for b in BRANDS
    if b["keywords"]
]


def brands_mentioned(text: str) -> list:
    """Return brand dicts whose name appears in free text."""
    return [b for b, pat in _KEYWORD_PATTERNS if pat.search(text or "")]


def is_official_domain(brand: dict, domain: str) -> bool:
    domain = (domain or "").lower().rstrip(".")
    return any(domain == d or domain.endswith("." + d) for d in brand["domains"])


def find_brand_by_name(name: str):
    for b in BRANDS:
        if b["name"] == name:
            return b
    return None
