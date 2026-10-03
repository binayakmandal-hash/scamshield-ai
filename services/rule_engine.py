"""Rule-based analyzer.

Two jobs:
  1. Offline fallback - the app still produces a complete, explainable
     analysis when no AI model is running, or the model fails.
  2. Transparent scoring - every point in the score comes from a named
     signal with a verbatim quote from the message.

Every piece of evidence is a regex match on the original text, so it can
never be fabricated.
"""
import re

LATIN = r"(?<![A-Za-z0-9])"  # word boundary that also works next to Indic text
END = r"(?![A-Za-z0-9])"


def _p(*parts):
    """Compile English patterns with boundaries, Indic patterns as-is."""
    compiled = []
    for part in parts:
        if re.search(r"[A-Za-z]", part) and not part.startswith("(?raw)"):
            compiled.append(re.compile(LATIN + "(?:" + part + ")" + END, re.I))
        else:
            compiled.append(re.compile(part.replace("(?raw)", ""), re.I))
    return compiled


# Each signal: id, title, points, severity, categories it hints at,
# explanation (shown to the user) and patterns that find verbatim evidence.
SIGNALS = [
    {
        "id": "urgency", "title": "Urgency / time pressure", "points": 20, "severity": "high",
        "categories": [],
        "explanation": "The message pressures the recipient to act immediately, which leaves less time to stop and verify.",
        "patterns": _p(
            r"within \d+\s*(?:minutes?|mins?|hours?|hrs?)", r"immediately", r"urgent(?:ly)?", r"act now",
            r"right now", r"today only", r"before midnight", r"last chance", r"limited (?:time|seats|period)",
            r"expires? (?:today|tonight|soon|in \d+)", r"offer expires", r"reply today", r"asap",
            r"(?:in|within) (?:the )?next \d+", r"तुरंत", r"आज रात", r"अभी", r"এখনই", r"অবিলম্বে", r"জরুরি",
        ),
    },
    {
        "id": "threat", "title": "Threat of loss or penalty", "points": 15, "severity": "high",
        "categories": [],
        "explanation": "The message warns of a negative consequence (blocking, suspension, penalty) to create fear.",
        "patterns": _p(
            r"(?:will|would) be (?:blocked|suspended|deactivated|disconnected|closed|cancelled|terminated|frozen)",
            r"account (?:is )?(?:blocked|suspended|on hold|locked)", r"legal action", r"penalty", r"arrest(?:ed)?",
            r"disconnect(?:ed|ion)?", r"काट दिया जाएगा", r"बंद (?:हो|कर) (?:जाएगा|दिया)", r"ব্লক", r"বন্ধ হয়ে যাবে",
        ),
    },
    {
        "id": "sensitive", "title": "Request for sensitive information", "points": 25, "severity": "high",
        "categories": ["Phishing"],
        "explanation": "The sender appears to ask for information that could be used to access an account or move money. "
                       "Genuine organisations do not ask for OTPs, PINs or passwords by message.",
        "patterns": _p(
            r"otp", r"one[- ]time password", r"upi pin", r"(?:atm |card )?pin", r"cvv", r"password",
            r"card (?:number|details)", r"(?:bank )?account (?:number|details)", r"bank details", r"ifsc",
            r"aadhaar|aadhar", r"pan (?:card|number)", r"login (?:details|credentials)", r"net ?banking",
            r"ओटीपी", r"पासवर्ड", r"ওটিপি", r"পিন",
        ),
    },
    {
        "id": "verify_account", "title": "Account verification request", "points": 15, "severity": "medium",
        "categories": ["Account verification scam", "Phishing"],
        "explanation": "Asking you to 'verify' or 'update' details through a message is a common way to collect login information.",
        "patterns": _p(
            r"verify (?:your )?(?:account|details|identity|kyc)", r"(?:update|complete) (?:your )?(?:kyc|pan|details|address)",
            r"kyc", r"re-?activate", r"confirm (?:your )?(?:account|details|identity)", r"verify immediately",
            r"update (?:your )?address",
        ),
    },
    {
        "id": "reward", "title": "Unrealistic reward", "points": 20, "severity": "high",
        "categories": ["Prize/lottery scam"],
        "explanation": "An unexpected prize or reward may be designed to trigger excitement and an impulsive response.",
        "patterns": _p(
            r"congratulations", r"you (?:have )?won", r"has won", r"winner", r"lottery", r"lucky draw", r"jackpot",
            r"prize", r"claim (?:your )?(?:reward|prize|gift)", r"free gift", r"cash ?back of", r"\d+\s*(?:lakh|crore)",
            r"इनाम", r"जीत", r"অভিনন্দন", r"পুরস্কার", r"জিতেছেন",
        ),
    },
    {
        "id": "fee", "title": "Upfront fee requested", "points": 20, "severity": "high",
        "categories": ["Payment/UPI fraud"],
        "explanation": "You are asked to pay before receiving something (a job, prize, scholarship or delivery). "
                       "Genuine offers rarely need an upfront payment through a message.",
        "patterns": _p(
            r"(?:registration|processing|security|verification|redelivery|delivery|clearance|joining|application|"
            r"refundable|release|handling|customs) (?:fee|charge|deposit|amount)",
            r"pay (?:a |the )?(?:small )?(?:fee|amount|rs\.?|₹)", r"security deposit", r"शुल्क", r"ফি",
        ),
    },
    {
        "id": "payment", "title": "Direct payment request", "points": 15, "severity": "high",
        "categories": ["Payment/UPI fraud"],
        "explanation": "The message asks you to send money directly (UPI, QR code or transfer). Payment requests should be "
                       "confirmed through a channel you already trust.",
        "patterns": _p(
            r"upi id", r"[a-z0-9._-]+@(?:ybl|ibl|axl|paytm|okaxis|oksbi|okhdfcbank|okicici|upi|apl)",
            r"scan (?:the |this )?qr", r"send money", r"transfer (?:the )?(?:amount|money|rs|₹)", r"collect request",
            r"gift card",
        ),
    },
    {
        "id": "job", "title": "Too-good-to-be-true job offer", "points": 15, "severity": "medium",
        "categories": ["Fake job/recruitment"],
        "explanation": "High pay for little work, no interview or 'no experience needed' are common traits of fake job offers.",
        "patterns": _p(
            r"work[- ]from[- ]home", r"part[- ]time (?:job|work)", r"earn (?:rs\.?|₹)?\s?[\d,]+(?:\s*[-–]\s*(?:rs\.?|₹)?\s?[\d,]+)? "
            r"(?:per|a|/) ?(?:day|week|hour)", r"no experience (?:needed|required)", r"daily (?:payment|income)",
            r"lik(?:e|ing) (?:youtube )?videos", r"hiring (?:now|immediately)",
        ),
    },
    {
        "id": "investment", "title": "Guaranteed or unusually high returns", "points": 20, "severity": "high",
        "categories": ["Investment/financial scam"],
        "explanation": "Promises of guaranteed or very high returns are a hallmark of investment fraud. Real investments carry risk.",
        "patterns": _p(
            r"guaranteed (?:returns?|profit|income)", r"double your money", r"\d+\s?% (?:daily|weekly|monthly|per day|returns?)",
            r"risk[- ]free", r"crypto(?:currency)? (?:trading|investment)", r"trading tips", r"stock tips",
        ),
    },
    {
        "id": "off_platform", "title": "Moves you to a private channel", "points": 10, "severity": "medium",
        "categories": [],
        "explanation": "Asking you to continue on WhatsApp, Telegram or a personal number takes the conversation away from "
                       "official, traceable channels.",
        "patterns": _p(r"whatsapp", r"telegram", r"t\.me/\S+", r"wa\.me/\S+", r"call (?:us |me )?(?:on|at)", r"dm me"),
    },
    {
        "id": "malware", "title": "Download or remote-access lure", "points": 20, "severity": "high",
        "categories": ["Malware/download lure"],
        "explanation": "Installing apps or files from a message, especially screen-sharing apps, can give someone else control of your device.",
        "patterns": _p(r"\.apk", r"download (?:the |our |this )?app", r"install (?:the |this )?(?:app|application|apk)",
                       r"anydesk", r"teamviewer", r"quick ?support", r"rustdesk", r"screen ?shar(?:e|ing)"),
    },
    {
        "id": "secrecy", "title": "Asks for secrecy", "points": 10, "severity": "medium",
        "categories": ["Romance/social engineering"],
        "explanation": "Being told not to tell anyone stops you from getting a second opinion.",
        "patterns": _p(r"(?:do not|don't) (?:tell|share this with|inform)", r"keep (?:this|it) (?:confidential|secret)"),
    },
    {
        "id": "generic_greeting", "title": "Generic greeting", "points": 5, "severity": "low",
        "categories": [],
        "explanation": "A generic greeting such as 'Dear Customer' suggests the message may have been sent in bulk "
                       "rather than to you personally. On its own this is a weak signal.",
        "patterns": _p(r"dear (?:customer|user|valued customer|account ?holder|winner|candidate|sir/madam|beneficiary)",
                       r"प्रिय ग्राहक", r"প্রিয় গ্রাহক"),
    },
    {
        "id": "delivery", "title": "Delivery problem notice", "points": 10, "severity": "medium",
        "categories": ["Delivery/package scam"],
        "explanation": "Unexpected 'failed delivery' messages are often used to collect a small fee or card details.",
        "patterns": _p(r"(?:package|parcel|shipment|consignment) (?:could not|couldn't|was not|is on hold|has been held)",
                       r"(?:incomplete|wrong|invalid) address", r"delivery (?:failed|attempt)", r"returned to (?:the )?sender",
                       r"held (?:at|in) customs"),
    },
    {
        "id": "support", "title": "Unsolicited 'customer support' contact", "points": 10, "severity": "medium",
        "categories": ["Fake customer support"],
        "explanation": "Support numbers sent in unsolicited messages may not belong to the organisation. Use the number on its official website or app.",
        "patterns": _p(r"customer (?:care|support|service) (?:number|executive|team)", r"helpline", r"refund (?:team|department)"),
    },
    {
        "id": "shouting", "title": "Excessive capitals or punctuation", "points": 5, "severity": "low",
        "categories": [],
        "explanation": "Shouting with capitals or repeated exclamation marks is a pressure tactic. On its own this is a weak signal.",
        "patterns": [re.compile(r"!{2,}"), re.compile(r"(?<![A-Za-z])[A-Z]{6,}(?![A-Za-z])")],
    },
]

# Categories suggested by context words, but only alongside a real warning signal.
# (name, context pattern, signals that must be present, weight used for ranking)
CONTEXT_CATEGORIES = [
    ("Fake scholarship", re.compile(r"scholarship|छात्रवृत्ति|বৃত্তি", re.I), {"fee", "sensitive", "payment", "reward"}, 40),
    ("Fake job/recruitment", re.compile(r"\bjob\b|hiring|recruit|\bhr\b|salary|vacancy|internship", re.I), {"fee", "job"}, 40),
    ("Banking fraud", re.compile(r"\bbank account\b|\bsbi\b|hdfc|icici|axis bank|kotak|net ?banking|\bkyc\b|बैंक|ব্যাংক", re.I),
     {"sensitive", "threat", "verify_account"}, 20),
    ("Delivery/package scam", re.compile(r"parcel|package|courier|shipment|delivery|india ?post", re.I),
     {"delivery"}, 40),
    ("Prize/lottery scam", re.compile(r"lottery|lucky draw|jackpot|\bwon\b|winner|पुरस्कार|इनाम|পুরস্কার", re.I), {"reward"}, 30),
    ("Payment/UPI fraud", re.compile(r"electricity|बिजली|বিদ্যুৎ|\bbill\b", re.I), {"threat"}, 15),
]
MAX_CATEGORIES = 3

RISK_BANDS = [(75, "Very High Risk"), (50, "High Risk"), (25, "Suspicious"), (0, "Low Risk")]


def level_for(score: int) -> str:
    for floor, label in RISK_BANDS:
        if score >= floor:
            return label
    return "Low Risk"


# Signals that are often mentioned as a *warning* in genuine messages
# ("we will never ask for your OTP"). A negation shortly before the match cancels it.
NEGATABLE = {"sensitive", "payment", "malware", "secrecy"}
NEGATION = re.compile(r"(?:never|not|n't|don't|do not|won't|will not|no one|nobody|avoid|beware|"
                      r"कभी नहीं|न करें|ना करें|মত|কখনো|করবেন না)[^.!?\n]{0,40}$", re.I)


# A sensitive item only counts as a *request* when an asking verb is nearby.
REQUEST = re.compile(r"share|send|enter|provide|submit|tell|give|reply|update|confirm|verify|fill|type|"
                     r"शेयर|बताएं|बताइए|भेजें|दें|दीजिए|শেয়ার|পাঠান|পাঠাও|দিন|বলুন|জানান", re.I)


_NEG_BEFORE = re.compile(r"(?:never|not|n't|don't|do not|won't|will not|no one|कभी|মত|কখনো)\W+(?:\w+\W+){0,2}$", re.I)


def _has_request(window: str) -> bool:
    """True if the window contains an asking verb that isn't itself negated ("never share")."""
    return any(not _NEG_BEFORE.search(window[:m.start()]) for m in REQUEST.finditer(window))


def _first_match(text, patterns, negatable=False, needs_request=False):
    best = None
    for pat in patterns:
        for m in pat.finditer(text):
            if negatable and NEGATION.search(text[max(0, m.start() - 60):m.start()]):
                continue  # e.g. "never share your OTP" is advice, not a request
            if needs_request and not _has_request(text[max(0, m.start() - 60):m.end() + 40]):
                continue  # e.g. "Your OTP is 4821" is a notification, not a request
            if best is None or m.start() < best.start():
                best = m
            break
    return best


def detect_signals(text: str) -> list:
    found = []
    for sig in SIGNALS:
        m = _first_match(text, sig["patterns"], negatable=sig["id"] in NEGATABLE,
                         needs_request=sig["id"] == "sensitive")
        if m:
            found.append({**sig, "evidence": m.group(0).strip()})
    return found


def _url_signal(urls, strict=False):
    # In emails, newsletters contain many long tracking links, so only clearly risky links count.
    risky = [u for u in urls if u["risk"] == "high" or (u["risk"] == "medium" and not strict)]
    if not risky:
        return None
    worst = max(risky, key=lambda u: u["points"])
    pts = 25 if worst["risk"] == "high" else 15
    reason = worst["flags"][0] if worst["flags"] else "unusual characteristics"
    return {
        "id": "link", "title": "Suspicious link", "points": pts, "severity": "high" if worst["risk"] == "high" else "medium",
        "categories": ["Phishing"],
        "evidence": worst["url"],
        "explanation": f"The message contains a link whose destination should be independently verified ({reason.lower()}). "
                       "ScamShield checked the link text only and did not open it.",
    }


def _impersonation_signal(text, urls, sender):
    claimed = sender.get("claimed_organizations") or []
    lookalike = [u for u in urls if u.get("resembles_brand")]
    mismatch = [o for o in sender.get("observations", []) if o["level"] == "warn" and "may not match" in o["text"]
                or "free provider" in o["text"]]
    if not (lookalike or (claimed and mismatch)):
        return None
    if lookalike:
        evidence = lookalike[0]["url"]
        org = lookalike[0]["resembles_brand"]
    else:
        org = claimed[0]
        email = next((e["address"] for e in sender.get("emails", [])), None)
        evidence = email or org
    return {
        "id": "impersonation", "title": "Possible impersonation", "points": 15, "severity": "high",
        "categories": ["Impersonation"],
        "evidence": evidence,
        "explanation": f"The message appears to present itself as {org}, but the link or sender details do not match that "
                       "organisation's official domains. This needs verification, though it is not proof on its own.",
    }


def build_actions(categories, signal_ids):
    actions = []
    if "link" in signal_ids or "verify_account" in signal_ids:
        actions.append("Don't open the link. Go to the organisation's official website or app by typing the address yourself.")
    if "sensitive" in signal_ids:
        actions.append("Never share passwords, OTPs, PINs, CVV or Aadhaar details in reply to a message or call.")
    if {"fee", "payment"} & signal_ids or "Payment/UPI fraud" in categories:
        actions.append("Don't send money or approve any UPI request based only on this message. Verify the request independently.")
    if "Fake job/recruitment" in categories:
        actions.append("Don't pay registration, training or security fees. Check the job on the company's official careers page.")
    if "Fake scholarship" in categories:
        actions.append("Check scholarships only on official portals (such as scholarships.gov.in) or with your institution's office.")
    if "Prize/lottery scam" in categories:
        actions.append("Remember that you can't win a lottery or contest you never entered. Don't pay a fee to 'release' a prize.")
    if "Delivery/package scam" in categories:
        actions.append("Track parcels only through the courier's official app or website using your own tracking number.")
    if "malware" in signal_ids:
        actions.append("Don't install apps, APK files or screen-sharing tools because a message asked you to.")
    if "off_platform" in signal_ids:
        actions.append("Be cautious about moving to WhatsApp, Telegram or a personal number; contact the organisation through official channels.")
    if signal_ids:
        actions.append("If you think you've been targeted, report it at cybercrime.gov.in or call the 1930 helpline (India). "
                       "If money was sent, contact your bank immediately.")
    if not actions:
        actions = [
            "No strong warning signs were found, but stay alert if anything feels unusual.",
            "If the message asks for anything unexpected later, verify it through an official channel.",
        ]
    # keep it concise
    return list(dict.fromkeys(actions))[:6]


def analyze(text: str, urls: list, sender: dict, strict_links: bool = False) -> dict:
    signals = detect_signals(text)
    for extra in (_url_signal(urls, strict_links), _impersonation_signal(text, urls, sender)):
        if extra:
            signals.append(extra)

    ids = {s["id"] for s in signals}
    # Rank categories by how many points of evidence point to them; keep the top few.
    cat_points = {}
    for s in signals:
        for c in s["categories"]:
            cat_points[c] = cat_points.get(c, 0) + s["points"]
    for name, pattern, needs, weight in CONTEXT_CATEGORIES:
        if pattern.search(text) and needs & ids:
            cat_points[name] = cat_points.get(name, 0) + weight
    categories = [c for c, _ in sorted(cat_points.items(), key=lambda kv: -kv[1])][:MAX_CATEGORIES]

    weak_only = all(s["severity"] == "low" for s in signals)
    score = min(100, sum(s["points"] for s in signals))
    level = level_for(score)
    if not categories:
        categories = ["Other"] if signals and not weak_only else []

    red_flags = [
        {"title": s["title"], "evidence": s["evidence"], "explanation": s["explanation"], "severity": s["severity"]}
        for s in signals
    ]
    breakdown = [{"signal": s["title"], "points": s["points"], "evidence": s["evidence"]} for s in signals]

    if not signals:
        summary = ("No common scam warning signs were detected in this message. That does not guarantee it is safe, "
                   "so stay cautious if it asks for money or personal details later.")
    else:
        names = ", ".join(s["title"].split(" /")[0].lower() for s in signals[:3])
        strength = "several characteristics" if len(signals) >= 3 else "some characteristics"
        summary = f"This message shows {strength} commonly associated with scams, including {names}."

    why = ("Scams work by creating pressure, excitement or fear so that people act before they think. "
           "The warning signs above are the specific techniques this message appears to use. Slowing down and "
           "verifying through a channel you already trust removes most of that pressure.") if signals else (
           "Even ordinary-looking messages can be part of a scam later in a conversation. The safest habit is to verify "
           "any request for money, codes or personal details through an official channel.")

    return {
        "risk_score": score,
        "risk_level": level,
        "categories": categories,
        "summary": summary,
        "red_flags": red_flags,
        "score_breakdown": breakdown,
        "why_it_matters": why,
        "recommended_actions": build_actions(categories, ids),
        "confidence_note": "This analysis is based on pattern matching of warning signs found in the text. "
                           "It is not proof that the message is or isn't fraudulent.",
        "language": "auto",
    }


# --------------------------------------------------------------------------- #
# Fallbacks for the follow-up features
# --------------------------------------------------------------------------- #
def action_plan(analysis: dict) -> list:
    level = analysis.get("risk_level", "Low Risk")
    cats = analysis.get("categories", [])
    if level == "Low Risk":
        return [
            {"title": "Read it calmly", "detail": "No strong warning signs were found. Still, take a moment before acting on any request."},
            {"title": "Verify anything unusual", "detail": "If it asks for money or details, confirm with the sender through a channel you already use."},
            {"title": "Keep a copy", "detail": "If something changes later, the original message helps you compare."},
        ]
    verify = "the organisation's official website or app"
    if "Fake job/recruitment" in cats:
        verify = "the company's official careers page"
    elif "Fake scholarship" in cats:
        verify = "your institution's office or the official scholarship portal"
    elif "Delivery/package scam" in cats:
        verify = "the courier's official app with your own tracking number"
    return [
        {"title": "Don't interact yet", "detail": "Don't reply, click links, call numbers in the message, pay or share any codes."},
        {"title": "Verify independently", "detail": f"Check the claim through {verify}. Type the address yourself instead of using any link in the message."},
        {"title": "Report and block", "detail": "Report the sender in your messaging app and block it. In India you can report at "
                                                "cybercrime.gov.in or call 1930; if money was sent, call your bank right away."},
    ]


def eli12(analysis: dict) -> str:
    level = analysis.get("risk_level", "Low Risk")
    flags = analysis.get("red_flags", [])
    if not flags:
        return ("We looked for the usual tricks scammers use and didn't find any. That's good! But if this message ever asks "
                "you for money or secret codes, ask a grown-up or someone you trust before doing anything.")
    tricks = "; ".join(f["title"].lower() for f in flags[:3])
    return (f"Think of this message like a stranger at the door. ScamShield rated it “{level}” because it uses tricks "
            f"that scammers use: {tricks}. Scammers try to make you rush, feel scared or feel excited so you don't stop "
            "to think. The best move is to not click, not pay and not share any codes. Instead, check with the real "
            "company yourself, or ask someone you trust.")


def chat_answer(question: str, analysis: dict) -> str:
    q = (question or "").lower()
    flags = analysis.get("red_flags", [])
    if any(w in q for w in ("verify", "check", "real", "genuine", "legit", "company")):
        return ("To verify it: find the organisation's official website or app yourself (search for it, don't use links in the "
                "message), use the contact details listed there, and ask whether they sent this message. For companies, "
                "check their official careers page and the company's registered details. Never verify by replying to the "
                "same number or email.")
    if any(w in q for w in ("share", "never", "information", "otp", "password")):
        return ("Never share OTPs, UPI PINs, ATM/card PINs, CVV numbers, passwords, net-banking logins or full card numbers. "
                "Be careful with Aadhaar, PAN and bank account details too. A genuine bank, company or government office "
                "will not ask for these through SMS, WhatsApp or a phone call.")
    if any(w in q for w in ("clicked", "paid", "sent money", "already", "shared")):
        return ("Act quickly: call your bank using the number on your card or official app to block transactions, change any "
                "passwords you entered, and report the incident at cybercrime.gov.in or by calling 1930 (India). Keep "
                "screenshots of the message as evidence.")
    if flags and any(w in q for w in ("worried", "which part", "worst", "most")):
        top = next((f for f in flags if f.get("severity") == "high"), flags[0])
        return f"The most concerning part is “{top['evidence']}” ({top['title'].lower()}). {top['explanation']}"
    if flags:
        listed = "; ".join(f"{f['title']} (“{f['evidence']}”)" for f in flags[:4])
        return f"{analysis.get('summary', '')} The main warning signs are: {listed}."
    return ("This message didn't show common scam warning signs. If you're unsure, verify it through an official channel "
            "you already trust before acting on it.")


FAMILY_TEMPLATES = {
    "en": {
        "risky": "\u26a0\ufe0f About the message you got: it shows signs of a scam ({signs}). Please don't click any link, "
                 "pay anything, or share OTPs, PINs or bank details. If it says it's from a bank or company, call them using "
                 "the number on their official website or your card. If you're unsure, call me first. - sent via ScamShield",
        "safe": "\u2705 About the message you got: I checked it and didn't find common scam warning signs. Still, if it ever "
                "asks for money, OTPs or bank details, check with me first. - sent via ScamShield",
    },
    "hi": {
        "risky": "\u26a0\ufe0f आपको जो मैसेज आया है उसमें धोखाधड़ी के संकेत हैं ({signs})। कृपया किसी लिंक पर क्लिक न करें, कोई पैसा न भेजें, "
                 "और OTP, PIN या बैंक की जानकारी किसी को न दें। अगर यह बैंक या कंपनी के नाम से है, तो उनकी आधिकारिक वेबसाइट या "
                 "कार्ड पर दिए नंबर पर ही फ़ोन करें। शक हो तो पहले मुझे फ़ोन करें। - sent via ScamShield",
        "safe": "\u2705 आपको जो मैसेज आया है, उसमें मुझे धोखाधड़ी के आम संकेत नहीं मिले। फिर भी अगर कभी पैसे, OTP या बैंक की "
                "जानकारी माँगी जाए, तो पहले मुझसे पूछ लें। - sent via ScamShield",
    },
    "bn": {
        "risky": "\u26a0\ufe0f তোমার কাছে যে মেসেজটা এসেছে, তাতে প্রতারণার লক্ষণ আছে ({signs})। কোনো লিংকে ক্লিক কোরো না, টাকা পাঠিও না, "
                 "আর OTP, PIN বা ব্যাংকের তথ্য কাউকে দিও না। ব্যাংক বা কোম্পানির নামে এলে তাদের অফিসিয়াল ওয়েবসাইট বা কার্ডে "
                 "দেওয়া নম্বরে ফোন করো। সন্দেহ হলে আগে আমাকে ফোন করো। - sent via ScamShield",
        "safe": "\u2705 তোমার কাছে আসা মেসেজটায় আমি প্রতারণার সাধারণ লক্ষণ পাইনি। তবুও কখনো টাকা, OTP বা ব্যাংকের তথ্য চাইলে "
                "আগে আমাকে জিজ্ঞেস কোরো। - sent via ScamShield",
    },
}


def family_note(analysis: dict, lang: str = "en") -> str:
    t = FAMILY_TEMPLATES.get(lang, FAMILY_TEMPLATES["en"])
    flags = analysis.get("red_flags", [])
    if analysis.get("risk_level") == "Low Risk" or not flags:
        return t["safe"]
    signs = ", ".join(f["title"].split(" /")[0].lower() for f in flags[:2])
    return t["risky"].format(signs=signs)
