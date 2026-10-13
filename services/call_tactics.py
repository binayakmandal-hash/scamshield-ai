"""Call copilot: pressure tactics scammers use on phone and video calls.

The browser turns speech into text (Web Speech API) and the page matches that text against these
patterns live, so nothing about the call is sent to ScamShield's server. The same patterns are used by
`scan()` here, which keeps them testable in Python. Patterns must stay valid in both Python and
JavaScript (no inline flags, no lookbehind, no \\b next to non-Latin text).
"""
from __future__ import annotations

import re

TACTICS = [
    {
        "id": "otp", "severity": "high",
        "title": {"en": "Asking for an OTP", "hi": "OTP माँगा जा रहा है", "bn": "OTP চাওয়া হচ্ছে"},
        "say": {"en": "Never read out an OTP. Say no and hang up.",
                "hi": "OTP कभी न बताएँ। मना करें और फ़ोन काट दें।",
                "bn": "OTP কখনো বলবেন না। না বলে ফোন কেটে দিন।"},
        "patterns": [r"\botp\b", r"one[- ]time password", r"\bcode\b.{0,30}(sent|received|aaya|message)", r"verification code",
                     r"ओटीपी", r"ওটিপি", r"कोड बताइए", r"কোডটা বলুন"],
    },
    {
        "id": "pin_card", "severity": "high",
        "title": {"en": "Asking for PIN or card details", "hi": "PIN या कार्ड की जानकारी माँगी जा रही है", "bn": "PIN বা কার্ডের তথ্য চাওয়া হচ্ছে"},
        "say": {"en": "No bank or officer ever needs your PIN, CVV or full card number.",
                "hi": "किसी बैंक या अधिकारी को आपका PIN, CVV या पूरा कार्ड नंबर नहीं चाहिए।",
                "bn": "কোনো ব্যাংক বা অফিসারের আপনার PIN, CVV বা পুরো কার্ড নম্বর লাগে না।"},
        "patterns": [r"\bupi pin\b", r"\batm pin\b", r"\bmpin\b", r"\bcvv\b", r"card (number|details|no)", r"expiry date",
                     r"net ?banking (password|login|id)", r"पिन (नंबर|बताइए|डालिए)", r"কার্ড নম্বর", r"पासवर्ड"],
    },
    {
        "id": "remote_app", "severity": "high",
        "title": {"en": "Asking you to install an app", "hi": "ऐप इंस्टॉल करवाया जा रहा है", "bn": "অ্যাপ ইনস্টল করতে বলা হচ্ছে"},
        "say": {"en": "Don't install anything. Screen-sharing apps let them see your PIN and OTPs.",
                "hi": "कुछ भी इंस्टॉल न करें। स्क्रीन-शेयरिंग ऐप से वे आपका PIN और OTP देख सकते हैं।",
                "bn": "কিছু ইনস্টল করবেন না। স্ক্রিন-শেয়ারিং অ্যাপে ওরা আপনার PIN আর OTP দেখতে পায়।"},
        "patterns": [r"any ?desk", r"team ?viewer", r"quick ?support", r"rust ?desk", r"air ?droid", r"screen ?shar",
                     r"(install|download) (this|the|an|our|ye|yeh)? ?(app|application|apk)", r"\bapk\b", r"एनीडेस्क", r"অ্যানিডেস্ক"],
    },
    {
        "id": "authority", "severity": "high",
        "title": {"en": "Claims to be police, CBI or customs", "hi": "पुलिस, CBI या कस्टम होने का दावा", "bn": "পুলিশ, CBI বা কাস্টমস বলে দাবি"},
        "say": {"en": "Real police never investigate or arrest anyone over a phone or video call. Hang up.",
                "hi": "असली पुलिस फ़ोन या वीडियो कॉल पर न जाँच करती है, न गिरफ़्तार। फ़ोन काट दें।",
                "bn": "আসল পুলিশ ফোন বা ভিডিও কলে তদন্ত বা গ্রেফতার করে না। ফোন কেটে দিন।"},
        "patterns": [r"\bcbi\b", r"crime branch", r"cyber (cell|crime)", r"narcotics", r"\bncb\b", r"customs", r"enforcement directorate",
                     r"\btrai\b", r"arrest warrant", r"digital arrest", r"money laundering", r"\bfir\b", r"drugs? (in|found)",
                     r"पुलिस", r"गिरफ्तार", r"गिरफ़्तार", r"পুলিশ", r"গ্রেফতার", r"গ্রেপ্তার"],
    },
    {
        "id": "secrecy", "severity": "high",
        "title": {"en": "Telling you to keep it secret", "hi": "किसी को न बताने को कहा जा रहा है", "bn": "কাউকে না বলতে বলা হচ্ছে"},
        "say": {"en": "Secrecy is the biggest warning sign. Tell someone now, even while they're on the line.",
                "hi": "राज़ रखने को कहना सबसे बड़ा खतरे का संकेत है। अभी किसी को बताइए।",
                "bn": "গোপন রাখতে বলাই সবচেয়ে বড় বিপদসংকেত। এখনই কাউকে জানান।"},
        "patterns": [r"(don'?t|do not|never) (tell|inform|share this with) (anyone|anybody|your (family|wife|husband|son|daughter|children))",
                     r"(keep|this is) (it |this )?(confidential|secret)", r"(don'?t|do not) (cut|disconnect|end) (the )?call",
                     r"stay on (the )?(video )?call", r"(camera|video) (on|band mat)", r"kisi ko mat bata", r"किसी को (मत|न) बता",
                     r"কাউকে (বলবেন|জানাবেন) না", r"call (mat|nahi) kaat"],
    },
    {
        "id": "safe_account", "severity": "high",
        "title": {"en": "Asking you to move money to a 'safe' account", "hi": "पैसे 'सुरक्षित' खाते में भेजने को कहा जा रहा है", "bn": "টাকা 'নিরাপদ' অ্যাকাউন্টে পাঠাতে বলা হচ্ছে"},
        "say": {"en": "There is no 'safe RBI account'. Anyone asking you to move money to one is stealing it.",
                "hi": "कोई 'सुरक्षित RBI खाता' नहीं होता। ऐसा कहने वाला पैसे चुरा रहा है।",
                "bn": "'নিরাপদ RBI অ্যাকাউন্ট' বলে কিছু নেই। যে এমন বলছে সে টাকা চুরি করছে।"},
        "patterns": [r"(safe|secure|rbi|verification|government|escrow) account", r"transfer (all |your |the )?(money|funds|savings|balance)",
                     r"(break|close) (your )?(fd|fixed deposit)", r"(will be|is) (refunded|returned) (after|once|within)",
                     r"सुरक्षित खाते", r"নিরাপদ অ্যাকাউন্ট"],
    },
    {
        "id": "account_block", "severity": "medium",
        "title": {"en": "Threat to block your account or SIM", "hi": "खाता या सिम बंद करने की धमकी", "bn": "অ্যাকাউন্ট বা সিম বন্ধের হুমকি"},
        "say": {"en": "Hang up and call your bank or operator yourself, on the number printed on your card or bill.",
                "hi": "फ़ोन काटें और कार्ड या बिल पर छपे नंबर पर खुद बैंक या कंपनी को कॉल करें।",
                "bn": "ফোন কেটে কার্ড বা বিলে ছাপা নম্বরে নিজে ব্যাংক বা অপারেটরকে ফোন করুন।"},
        "patterns": [r"\bkyc\b", r"(account|card|sim|number|connection) (will be |is being |has been )?(blocked|suspended|deactivated|disconnected|closed)",
                     r"block ho jayega", r"बंद हो जाएगा", r"ব্লক হয়ে যাবে", r"বন্ধ হয়ে যাবে"],
    },
    {
        "id": "money_bait", "severity": "medium",
        "title": {"en": "Refund, cashback or prize offer", "hi": "रिफ़ंड, कैशबैक या इनाम का लालच", "bn": "রিফান্ড, ক্যাশব্যাক বা পুরস্কারের লোভ"},
        "say": {"en": "Real refunds arrive on their own. You never pay, scan or share a code to receive money.",
                "hi": "असली रिफ़ंड अपने-आप आता है। पैसे पाने के लिए कभी भुगतान, स्कैन या कोड नहीं देना पड़ता।",
                "bn": "আসল রিফান্ড নিজে থেকেই আসে। টাকা পেতে কখনো পে, স্ক্যান বা কোড দিতে হয় না।"},
        "patterns": [r"\brefund\b", r"cash ?back", r"lottery", r"\bprize\b", r"\bkbc\b", r"lucky draw", r"you (have )?won",
                     r"इनाम", r"लॉटरी", r"লটারি", r"পুরস্কার"],
    },
    {
        "id": "receive_trick", "severity": "high",
        "title": {"en": "'Scan or approve to receive money'", "hi": "'पैसे पाने के लिए स्कैन/मंज़ूर करें'", "bn": "'টাকা পেতে স্ক্যান/অনুমোদন করুন'"},
        "say": {"en": "Scanning a QR or approving a request always SENDS your money. Refuse.",
                "hi": "QR स्कैन करने या अनुरोध मंज़ूर करने से हमेशा आपके पैसे जाते हैं। मना करें।",
                "bn": "QR স্ক্যান বা অনুরোধ অনুমোদন করলে সবসময় আপনার টাকা যায়। না বলুন।"},
        "patterns": [r"scan (the|this) qr", r"approve (the |this )?(request|payment)", r"(to|you will) (receive|get) (the |your )?(money|payment|refund)",
                     r"collect request", r"enter (your )?pin to (receive|get)"],
    },
    {
        "id": "family_emergency", "severity": "high",
        "title": {"en": "A family emergency needing money", "hi": "परिवार की इमरजेंसी के लिए पैसे", "bn": "পরিবারের জরুরি অবস্থায় টাকা চাওয়া"},
        "say": {"en": "Voices can be faked with AI. Hang up and call your family member on their own number.",
                "hi": "AI से आवाज़ नकली बनाई जा सकती है। फ़ोन काटकर परिवार वाले को उनके अपने नंबर पर कॉल करें।",
                "bn": "AI দিয়ে গলা নকল করা যায়। ফোন কেটে পরিবারের মানুষটিকে তাঁর নিজের নম্বরে ফোন করুন।"},
        "patterns": [r"(your )?(son|daughter|beta|beti|husband|grandson|nephew) .{0,30}(arrested|accident|hospital|police station|in trouble)",
                     r"(had|met with) an accident", r"(send|need) (the )?money (urgently|right now|immediately)",
                     r"(don'?t|do not) tell (mom|dad|papa|mummy|mother|father)", r"बेटा.{0,20}(पकड़ा|गिरफ्तार|हादसा)"],
    },
    {
        "id": "urgency", "severity": "low",
        "title": {"en": "Rushing you", "hi": "जल्दबाज़ी करवाई जा रही है", "bn": "তাড়াহুড়ো করানো হচ্ছে"},
        "say": {"en": "Pressure to act now is a trick. Say 'I'll call back' and hang up.",
                "hi": "अभी करने का दबाव एक चाल है। कहें 'मैं बाद में कॉल करूँगा' और फ़ोन काट दें।",
                "bn": "এখনই করার চাপ একটা কৌশল। বলুন 'পরে ফোন করব' আর ফোন কেটে দিন।"},
        "patterns": [r"immediately", r"right now", r"within (\d+|two|five|ten|thirty) (minutes|mins|hours)", r"last chance", r"\burgent",
                     r"\babhi\b", r"jaldi", r"तुरंत", r"अभी", r"এখনই", r"তাড়াতাড়ি"],
    },
    {
        "id": "odd_payment", "severity": "high",
        "title": {"en": "Paying by gift card or crypto", "hi": "गिफ़्ट कार्ड या क्रिप्टो से भुगतान", "bn": "গিফট কার্ড বা ক্রিপ্টোতে পেমেন্ট"},
        "say": {"en": "No government office or company takes fines in gift cards or crypto.",
                "hi": "कोई सरकारी दफ़्तर या कंपनी गिफ़्ट कार्ड या क्रिप्टो में जुर्माना नहीं लेती।",
                "bn": "কোনো সরকারি অফিস বা কোম্পানি গিফট কার্ড বা ক্রিপ্টোতে জরিমানা নেয় না।"},
        "patterns": [r"gift ?card", r"(google )?play (store )?card", r"amazon (pay )?voucher", r"bitcoin", r"\bcrypto", r"\busdt\b"],
    },
]

_COMPILED = [(t, [re.compile(p, re.I) for p in t["patterns"]]) for t in TACTICS]


def for_client() -> list[dict]:
    """The tactic list as sent to the browser (all three languages; the page picks one)."""
    return [{"id": t["id"], "severity": t["severity"], "title": t["title"], "say": t["say"], "patterns": t["patterns"]}
            for t in TACTICS]


def scan(transcript: str) -> list[dict]:
    """Return the tactics heard in a transcript, in the order they first appear."""
    hits = []
    for tactic, patterns in _COMPILED:
        positions = [m.start() for p in patterns for m in [p.search(transcript or "")] if m]
        if positions:
            hits.append((min(positions), tactic["id"]))
    return [{"id": tid, "at": pos} for pos, tid in sorted(hits)]


def risk(hit_ids: list[str]) -> str:
    """Overall level for the call so far: 'scam' after two high-severity tactics, 'warning' after one (or any two)."""
    sev = {t["id"]: t["severity"] for t in TACTICS}
    high = sum(1 for h in hit_ids if sev.get(h) == "high")
    if high >= 2:
        return "scam"
    if high == 1 or len(hit_ids) >= 2:
        return "warning"
    return "listening" if not hit_ids else "caution"
