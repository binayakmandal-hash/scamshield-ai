"""Safe, text-only URL analysis.

IMPORTANT: nothing in this module ever opens, resolves or fetches a URL.
Every check is done on the characters of the link itself.
"""
import ipaddress
import re
from urllib.parse import urlsplit

from .brands import BRANDS, is_official_domain

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "ow.ly",
    "shorturl.at", "tiny.cc", "rebrand.ly", "s.id", "buff.ly", "t.ly", "bit.do", "v.gd",
    "shorte.st", "tiny.one", "surl.li", "u.to", "clck.ru", "qr.ae", "lnkd.in", "wa.link",
}

# TLDs that are cheap/free and appear disproportionately in phishing reports.
RISKY_TLDS = {
    "xyz", "top", "click", "live", "loan", "work", "zip", "mov", "icu", "buzz", "rest",
    "cfd", "sbs", "online", "site", "shop", "info", "tk", "ml", "ga", "cf", "gq", "support",
    "win", "bid", "country", "kim", "monster", "quest", "cyou",
}

# Second-level suffixes, so "example.co.in" is treated as one registrable domain.
MULTI_PART_SUFFIXES = {
    "co.in", "gov.in", "org.in", "ac.in", "edu.in", "net.in", "res.in", "nic.in", "bank.in",
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.jp", "com.br", "in.net",
}

LURE_WORDS = ["login", "signin", "verify", "update", "kyc", "secure", "account", "wallet",
              "reward", "claim", "bonus", "refund", "unlock", "confirm", "otp", "pay"]

COMMON_TLDS = (
    "com|in|net|org|co|io|xyz|top|info|online|site|shop|live|click|link|me|app|ly|gl|gd|at|"
    "tk|ml|ga|cf|gq|icu|buzz|support|win|biz|us|uk|cc|to|gov|edu|ac|bank|sbi|club|store|"
    "tech|vip|work|loan|cfd|sbs|rest|zip|mov|quest|cyou|monster|kim|bid|country"
)

URL_RE = re.compile(
    r"(?:(?:https?|hxxps?)://[^\s<>\"']+)"
    r"|(?:www\.[^\s<>\"']+)"
    r"|(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + COMMON_TLDS + r")"
    r"(?:/[^\s<>\"']*)?(?![\w@-]|\.\w)",
    re.IGNORECASE,
)

_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def defang(url: str) -> str:
    """Make a URL non-clickable for display, e.g. https://a.com -> hxxps://a[.]com"""
    return url.replace("http", "hxxp", 1).replace(".", "[.]")


def registered_domain(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def extract_urls(text: str) -> list:
    found, seen = [], set()
    for m in URL_RE.finditer(text or ""):
        url = m.group(0).rstrip(".,;:!?)]}'\"")
        if len(url) < 4 or url.lower() in seen:
            continue
        # skip things like "Rs.500" or version numbers that slipped through
        if re.fullmatch(r"[\d.]+", url):
            continue
        seen.add(url.lower())
        found.append(url)
    return found


def _brand_resemblance(host: str, reg_domain: str):
    """Return (brand_name, reason) if the host imitates a known brand."""
    host_l = host.lower()
    normalized = host_l.translate(_LEET)
    reg_label = reg_domain.split(".")[0]

    for brand in BRANDS:
        if is_official_domain(brand, host_l):
            return None
        for token in brand["tokens"]:
            if len(token) < 3:
                continue
            if token in host_l:
                return brand["name"], f"Contains “{token}” but is not an official {brand['name']} domain"
            if token in normalized and token not in host_l:
                return brand["name"], f"Uses look-alike characters to spell “{token}”"
        for official in brand["domains"]:
            off_label = official.split(".")[0]
            if len(off_label) >= 5 and 0 < _levenshtein(reg_label, off_label) <= 1:
                return brand["name"], f"One character away from the official domain {official}"
    return None


def analyze_url(url: str) -> dict:
    raw = url
    has_scheme = bool(re.match(r"^(?:https?|hxxps?)://", url, re.I))
    parsed = urlsplit(url if has_scheme else "http://" + url)
    host = (parsed.hostname or "").lower()
    scheme = parsed.scheme.lower().replace("hxxp", "http") if has_scheme else None

    reg = registered_domain(host) if host else ""
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    sub_part = host[: -len(reg)].rstrip(".") if reg and host.endswith(reg) else ""
    subdomains = [s for s in sub_part.split(".") if s and s != "www"]

    flags = []  # (points, message)
    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
        flags.append((30, "Uses a raw IP address instead of a domain name"))
    except ValueError:
        pass

    is_shortener = reg in SHORTENERS or host in SHORTENERS
    if is_shortener:
        flags.append((20, "URL shortener hides the real destination"))

    if scheme == "http":
        flags.append((10, "Uses plain HTTP, so the connection is not encrypted"))
    elif scheme is None:
        flags.append((0, "No http/https shown; the destination protocol is unknown"))

    if tld in RISKY_TLDS:
        flags.append((15, f"Uses the .{tld} ending, which is common in throwaway sites"))

    if "xn--" in host or any(ord(ch) > 127 for ch in raw):
        flags.append((25, "Contains unusual or international characters that can imitate normal letters"))

    if "@" in (parsed.netloc or ""):
        flags.append((25, "Contains '@' in the address, which can disguise the real destination"))

    if len(subdomains) >= 3:
        flags.append((10, f"Has many subdomains ({len(subdomains)})"))

    reg_label = reg.split(".")[0] if reg else ""
    if reg_label.count("-") >= 2:
        flags.append((10, "Domain name contains several hyphens"))

    if len(raw) > 80:
        flags.append((5, "Very long link"))

    path_l = (parsed.path + "?" + (parsed.query or "")).lower() + " " + host
    lures = [w for w in LURE_WORDS if w in path_l]
    if lures:
        flags.append((10, "Contains action words often used in phishing links: " + ", ".join(lures[:4])))

    resemblance = _brand_resemblance(host, reg) if host and not is_ip else None
    if resemblance:
        flags.append((30, resemblance[1]))

    points = min(100, sum(p for p, _ in flags))
    risk = "high" if points >= 35 else "medium" if points >= 15 else "low"

    return {
        "url": raw,
        "defanged": defang(raw),
        "host": host,
        "domain": reg,
        "uses_https": True if scheme == "https" else (False if scheme == "http" else None),
        "is_shortener": is_shortener,
        "is_ip_address": is_ip,
        "subdomains": subdomains,
        "resembles_brand": resemblance[0] if resemblance else None,
        "flags": [m for p, m in flags if m],
        "risk": risk,
        "points": points,
    }


def analyze_urls(text: str) -> list:
    return [analyze_url(u) for u in extract_urls(text)]
