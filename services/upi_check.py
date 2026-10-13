"""UPI translator: says in plain words what will REALLY happen if you scan, approve or pay.

The most common UPI trick in India is a lie about direction: "scan this QR to receive the money",
"approve the request to get your refund", "enter your PIN to accept the cashback". On UPI, a PIN is only
ever used to send money out. This module reads a QR code, a payment-request screenshot or pasted text,
works out which way the money would move, to whom and how much, and explains it in English, Hindi or
Bengali.

Everything here is deterministic: no AI is needed, and nothing is guessed. If the image or text holds no
payment, we say so instead of inventing one.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from .brands import BRANDS
from .url_analyzer import analyze_url

LANGS = ("en", "hi", "bn")

# Common UPI handles (the part after @) and the app or bank behind them. Not exhaustive.
HANDLES = {
    "ybl": "PhonePe", "ibl": "PhonePe", "axl": "PhonePe",
    "okaxis": "Google Pay", "okhdfcbank": "Google Pay", "okicici": "Google Pay", "oksbi": "Google Pay",
    "paytm": "Paytm", "ptyes": "Paytm", "ptsbi": "Paytm", "pthdfc": "Paytm", "ptaxis": "Paytm",
    "apl": "Amazon Pay", "yapl": "Amazon Pay", "rapl": "Amazon Pay",
    "upi": "BHIM", "sbi": "SBI", "hdfcbank": "HDFC Bank", "icici": "ICICI Bank", "axisbank": "Axis Bank",
    "kotak": "Kotak", "pnb": "PNB", "barodampay": "Bank of Baroda", "boi": "Bank of India", "cnrb": "Canara Bank",
    "freecharge": "Freecharge", "jupiteraxis": "Jupiter", "fam": "FamPay", "slc": "Slice", "naviaxis": "Navi",
    "superyes": "super.money", "waicici": "WhatsApp Pay", "wahdfcbank": "WhatsApp Pay", "waaxis": "WhatsApp Pay",
    "wasbi": "WhatsApp Pay", "timecosmos": "Cred", "axisb": "Cred", "yesbank": "Yes Bank", "idfcbank": "IDFC First",
}

VPA_RE = re.compile(r"\b([A-Za-z0-9._-]{2,64})@([A-Za-z][A-Za-z0-9]{1,24})\b(?!\.[A-Za-z])")  # not an email address
AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr)\s?(\d[\d,]*(?:\.\d{1,2})?)", re.I)
PAYMENT_APPS = {"Paytm", "PhonePe", "Google Pay"}
REQUESTER_RE = re.compile(r"(?:^|[.!\n]\s*)([A-Z][A-Za-z.]*(?: [A-Z][A-Za-z.]*){0,3}) (?:has requested|is requesting|requested)")
EMAIL_TLDS = re.compile(r"^(gmail|yahoo|outlook|hotmail|rediffmail|icloud|proton|live)$", re.I)

# --------------------------------------------------------------------------- #
# Text cues
# --------------------------------------------------------------------------- #
CUES = {
    "receive_trick": re.compile(
        r"(to|and|will|you('ll| will)?|for) (receive|get|accept|claim) (the |your |a )?(money|payment|amount|refund|cashback|reward|prize|₹|rs)"
        r"|(scan|approve|accept|enter (your )?(upi )?pin).{0,40}(receive|get (the|your) (money|refund|payment)|credited)"
        r"|pin (daal|dalo|dalein|daaliye).{0,30}(paisa|paise) (aa|milenge|aayenge)"
        r"|पैसे (प्राप्त|मिल)|টাকা (পেতে|পাবেন)", re.I),
    "collect": re.compile(
        r"collect request|payment request|request(ed|ing)? (money|payment|₹|rs|inr)|is requesting|has requested"
        r"|request from|pay request|approve (the |this )?(request|payment)|requested you to pay|mandate", re.I),
    "pin": re.compile(r"(enter|type|put|share|daal\w*) (your |the )?(upi )?(pin|mpin)|upi pin|यूपीआई पिन|ইউপিআই পিন", re.I),
    "refund_bait": re.compile(r"\b(refund|cashback|reward|bonus|prize|lottery|won|winner|kbc|lucky draw|gift)\b", re.I),
    "mistake": re.compile(r"(sent|paid|transferred|credited) (to you )?(by mistake|wrongly|accidentally)|wrong (number|account|transfer)"
                          r"|(return|send back|refund) (the |my )?(extra |excess )?(money|amount)|galti se", re.I),
    "urgency": re.compile(r"(expires?|valid)\s+(in|within|for)\s+\d+|within\s+\d+ ?(min|minutes|hours?)|immediately|urgent|right now|jaldi", re.I),
    "remote": re.compile(r"anydesk|teamviewer|quick ?support|rustdesk|airdroid|screen ?shar", re.I),
    "credited_sms": re.compile(r"(credited|received) (to|in|into) (your )?(a/?c|account|bank)|has been credited|is credited|credited with", re.I),
}

# --------------------------------------------------------------------------- #
# Strings (en / hi / bn)
# --------------------------------------------------------------------------- #
S = {
    "truth_qr": {
        "en": "If you scan this and enter your UPI PIN, {amount} will LEAVE your account and go to {payee}.",
        "hi": "अगर आप इसे स्कैन करके UPI PIN डालते हैं, तो {amount} आपके खाते से कटकर {payee} को चला जाएगा।",
        "bn": "এটা স্ক্যান করে UPI PIN দিলে {amount} আপনার অ্যাকাউন্ট থেকে কেটে {payee}-এর কাছে চলে যাবে।",
    },
    "truth_collect": {
        "en": "This is a request for you to PAY {amount} to {payee}. If you approve it and enter your PIN, the money leaves your account. You will not receive anything.",
        "hi": "यह {payee} को {amount} भेजने का अनुरोध है। अगर आप इसे मंज़ूर करके PIN डालते हैं, तो पैसे आपके खाते से जाएंगे। आपको कुछ नहीं मिलेगा।",
        "bn": "এটা {payee}-কে {amount} পাঠানোর অনুরোধ। অনুমোদন করে PIN দিলে টাকা আপনার অ্যাকাউন্ট থেকে যাবে। আপনি কিছুই পাবেন না।",
    },
    "truth_pin": {
        "en": "Whatever the message says, a UPI PIN is only ever used to SEND money. You never need it, or a QR scan, to receive money.",
        "hi": "संदेश में चाहे जो लिखा हो, UPI PIN सिर्फ़ पैसे भेजने के लिए होता है। पैसे पाने के लिए न PIN चाहिए, न QR स्कैन।",
        "bn": "মেসেজে যা-ই লেখা থাকুক, UPI PIN শুধু টাকা পাঠাতে লাগে। টাকা পেতে PIN বা QR স্ক্যান কোনোটাই লাগে না।",
    },
    "truth_pay": {
        "en": "Paying this sends {amount} from your account to {payee}. Nothing comes back to you.",
        "hi": "यह भुगतान करने पर {amount} आपके खाते से {payee} को जाएगा। आपको बदले में कुछ नहीं आएगा।",
        "bn": "এটা পে করলে {amount} আপনার অ্যাকাউন্ট থেকে {payee}-এর কাছে যাবে। আপনার কাছে কিছু ফিরে আসবে না।",
    },
    "truth_mistake": {
        "en": "Someone says they sent you money by mistake and wants it back. Open your bank app yourself first: fake 'credited' messages are common, and the money often never arrived.",
        "hi": "कोई कह रहा है कि उसने गलती से आपको पैसे भेजे और अब वापस चाहिए। पहले खुद अपना बैंक ऐप खोलकर देखें: नकली 'क्रेडिट' संदेश आम हैं, और अक्सर पैसे आए ही नहीं होते।",
        "bn": "কেউ বলছেন ভুল করে আপনাকে টাকা পাঠিয়েছেন, এখন ফেরত চান। আগে নিজে ব্যাংকের অ্যাপ খুলে দেখুন: ভুয়ো 'ক্রেডিট' মেসেজ খুব চলে, প্রায়ই টাকা আসেইনি।",
    },
    "truth_credited": {
        "en": "This says money was credited to you. You don't need to do anything. Check your bank app yourself before believing it, and never 'send back' money because someone asks.",
        "hi": "इसमें लिखा है कि आपके खाते में पैसे आए हैं। आपको कुछ करने की ज़रूरत नहीं है। पहले खुद अपने बैंक ऐप में जाँचें, और किसी के कहने पर पैसे 'वापस' न भेजें।",
        "bn": "এতে বলা হয়েছে আপনার অ্যাকাউন্টে টাকা এসেছে। আপনাকে কিছু করতে হবে না। আগে নিজে ব্যাংকের অ্যাপে দেখে নিন, আর কেউ বললেই টাকা 'ফেরত' পাঠাবেন না।",
    },
    "truth_link": {
        "en": "This QR code doesn't make a payment. It opens a website: {domain}. Treat it like any link from a stranger.",
        "hi": "यह QR कोड भुगतान नहीं करता, यह एक वेबसाइट खोलता है: {domain}। इसे किसी अनजान लिंक की तरह ही समझें।",
        "bn": "এই QR কোড পেমেন্ট করে না, একটা ওয়েবসাইট খোলে: {domain}। অচেনা লিঙ্কের মতোই সাবধান থাকুন।",
    },
    "truth_none": {
        "en": "We couldn't find a UPI QR, payment request or payment details in this. Try a clearer screenshot or paste the message text.",
        "hi": "इसमें कोई UPI QR, भुगतान अनुरोध या भुगतान की जानकारी नहीं मिली। साफ़ स्क्रीनशॉट आज़माएँ या संदेश का टेक्स्ट चिपकाएँ।",
        "bn": "এতে কোনো UPI QR, পেমেন্ট অনুরোধ বা পেমেন্টের তথ্য পাওয়া যায়নি। আরও পরিষ্কার স্ক্রিনশট দিন বা মেসেজের লেখা পেস্ট করুন।",
    },
    "any_amount": {"en": "whatever amount you type", "hi": "जितनी रकम आप डालेंगे", "bn": "যত টাকা আপনি লিখবেন"},
    "the_amount": {"en": "the amount shown", "hi": "दिखाई गई रकम", "bn": "দেখানো টাকা"},
    "someone": {"en": "the person who sent it", "hi": "भेजने वाले व्यक्ति", "bn": "যিনি পাঠিয়েছেন"},
    "head_danger": {"en": "Stop. This takes money from you.", "hi": "रुकिए। इससे आपके पैसे जाएंगे।", "bn": "থামুন। এতে আপনার টাকা যাবে।"},
    "head_caution": {"en": "This sends money. Check who gets it.", "hi": "इससे पैसे भेजे जाएंगे। देख लें किसे।", "bn": "এতে টাকা যাবে। দেখে নিন কাকে।"},
    "head_info": {"en": "Nothing to pay here.", "hi": "यहाँ कुछ भुगतान नहीं करना है।", "bn": "এখানে কিছু দিতে হবে না।"},
    "head_none": {"en": "No payment found.", "hi": "कोई भुगतान नहीं मिला।", "bn": "কোনো পেমেন্ট পাওয়া যায়নি।"},
    "head_link": {"en": "This QR opens a website.", "hi": "यह QR एक वेबसाइट खोलता है।", "bn": "এই QR একটা ওয়েবসাইট খোলে।"},
}

FLAGS = {
    "receive_trick": ("high", {
        "en": ("They say you'll RECEIVE money", "You never scan, approve or enter a PIN to receive money. Saying so is the trick itself."),
        "hi": ("कहा जा रहा है कि आपको पैसे मिलेंगे", "पैसे पाने के लिए कभी स्कैन, मंज़ूरी या PIN की ज़रूरत नहीं होती। यही असली चाल है।"),
        "bn": ("বলা হচ্ছে আপনি টাকা পাবেন", "টাকা পেতে কখনো স্ক্যান, অনুমোদন বা PIN লাগে না। এটাই আসল ফাঁদ।"),
    }),
    "collect": ("medium", {
        "en": ("It's a payment request", "A 'collect request' asks YOU to pay. Approving it moves money out of your account."),
        "hi": ("यह भुगतान अनुरोध है", "'कलेक्ट रिक्वेस्ट' आपसे पैसे माँगती है। मंज़ूर करते ही पैसे आपके खाते से जाते हैं।"),
        "bn": ("এটা একটা পেমেন্ট অনুরোধ", "'কালেক্ট রিকোয়েস্ট' আপনার কাছে টাকা চায়। অনুমোদন করলেই টাকা আপনার অ্যাকাউন্ট থেকে যায়।"),
    }),
    "pin": ("high", {
        "en": ("Asks for your UPI PIN", "Your PIN approves a payment out of your account. Nobody else ever needs it."),
        "hi": ("आपका UPI PIN माँगा जा रहा है", "PIN आपके खाते से भुगतान को मंज़ूरी देता है। किसी और को इसकी कभी ज़रूरत नहीं होती।"),
        "bn": ("আপনার UPI PIN চাওয়া হচ্ছে", "PIN আপনার অ্যাকাউন্ট থেকে পেমেন্ট অনুমোদন করে। অন্য কারও এটা কখনো লাগে না।"),
    }),
    "refund_bait": ("medium", {
        "en": ("Promises a refund, cashback or prize", "Real refunds and cashback arrive on their own. They never need you to pay or approve anything."),
        "hi": ("रिफ़ंड, कैशबैक या इनाम का वादा", "असली रिफ़ंड और कैशबैक अपने-आप आते हैं। उनके लिए कभी भुगतान या मंज़ूरी नहीं देनी पड़ती।"),
        "bn": ("রিফান্ড, ক্যাশব্যাক বা পুরস্কারের প্রতিশ্রুতি", "আসল রিফান্ড বা ক্যাশব্যাক নিজে থেকেই আসে। তার জন্য কখনো টাকা দিতে বা অনুমোদন করতে হয় না।"),
    }),
    "mistake": ("high", {
        "en": ("'Sent by mistake, please return'", "A fake 'credited' SMS followed by a request to return money is a common trick. Check your bank app first; the money usually never arrived."),
        "hi": ("'गलती से भेज दिया, लौटा दीजिए'", "नकली 'क्रेडिट' SMS भेजकर पैसे लौटाने को कहना आम चाल है। पहले अपना बैंक ऐप देखें, अक्सर पैसे आए ही नहीं होते।"),
        "bn": ("'ভুল করে পাঠিয়েছি, ফেরত দিন'", "ভুয়ো 'ক্রেডিট' SMS পাঠিয়ে টাকা ফেরত চাওয়া একটা চেনা কৌশল। আগে ব্যাংকের অ্যাপ দেখুন, প্রায়ই টাকা আসেইনি।"),
    }),
    "urgency": ("low", {
        "en": ("Rushes you", "A countdown or 'do it now' is meant to stop you from checking."),
        "hi": ("जल्दबाज़ी करवाई जा रही है", "उल्टी गिनती या 'अभी करें' इसलिए है ताकि आप जाँच न कर सकें।"),
        "bn": ("তাড়াহুড়ো করানো হচ্ছে", "কাউন্টডাউন বা 'এখনই করুন' বলা হয় যাতে আপনি যাচাই না করেন।"),
    }),
    "remote": ("high", {
        "en": ("Mentions a screen-sharing app", "Apps like AnyDesk let a stranger see your screen, including your PIN and OTPs."),
        "hi": ("स्क्रीन-शेयरिंग ऐप का ज़िक्र", "AnyDesk जैसे ऐप से अजनबी आपकी स्क्रीन, PIN और OTP देख सकता है।"),
        "bn": ("স্ক্রিন-শেয়ারিং অ্যাপের উল্লেখ", "AnyDesk-এর মতো অ্যাপে অচেনা লোক আপনার স্ক্রিন, PIN আর OTP দেখতে পায়।"),
    }),
    "prefilled": ("low", {
        "en": ("Amount is already filled in: {amount}", "The QR fixes how much you'll pay. Make sure it's what you agreed to."),
        "hi": ("रकम पहले से भरी है: {amount}", "QR में तय है कि आप कितना भेजेंगे। देख लें कि यही रकम तय हुई थी।"),
        "bn": ("টাকার অঙ্ক আগে থেকেই বসানো: {amount}", "QR-এ ঠিক করা আছে আপনি কত দেবেন। মিলিয়ে নিন এটাই কথা হয়েছিল কি না।"),
    }),
    "brand_mismatch": ("high", {
        "en": ("Claims to be {brand}, but pays {name}", "The name on the payment doesn't match the company the message claims to be from."),
        "hi": ("{brand} होने का दावा, पर पैसे {name} को जाएंगे", "भुगतान पर लिखा नाम उस कंपनी से मेल नहीं खाता जिसका संदेश में दावा है।"),
        "bn": ("{brand} বলে দাবি, কিন্তু টাকা যাবে {name}-এর কাছে", "পেমেন্টের নাম মেসেজে দাবি করা কোম্পানির সঙ্গে মেলে না।"),
    }),
    "personal_vpa": ("low", {
        "en": ("Pays a personal account", "The UPI ID is a phone number, so the money goes to an individual, not a business."),
        "hi": ("व्यक्तिगत खाते में भुगतान", "UPI ID एक फ़ोन नंबर है, यानी पैसे किसी कंपनी को नहीं, एक व्यक्ति को जाएंगे।"),
        "bn": ("ব্যক্তিগত অ্যাকাউন্টে পেমেন্ট", "UPI ID একটা ফোন নম্বর, মানে টাকা কোনো ব্যবসায় নয়, একজন ব্যক্তির কাছে যাবে।"),
    }),
    "unknown_handle": ("low", {
        "en": ("Unfamiliar UPI handle: @{handle}", "This isn't one of the common UPI apps or banks we know. That alone isn't proof of fraud."),
        "hi": ("अनजान UPI हैंडल: @{handle}", "यह हमारी जानकारी वाले आम UPI ऐप या बैंक में नहीं है। सिर्फ़ इससे धोखा साबित नहीं होता।"),
        "bn": ("অচেনা UPI হ্যান্ডেল: @{handle}", "এটা আমাদের জানা সাধারণ UPI অ্যাপ বা ব্যাংকের মধ্যে নেই। শুধু এতে প্রতারণা প্রমাণ হয় না।"),
    }),
    "risky_link": ("high", {
        "en": ("The website looks risky", "{why}"),
        "hi": ("वेबसाइट जोखिम भरी लगती है", "{why}"),
        "bn": ("ওয়েবসাইটটা ঝুঁকিপূর্ণ মনে হচ্ছে", "{why}"),
    }),
}

STEPS = {
    "danger": {
        "en": ["Don't scan, approve or enter your PIN.", "Decline the request in your UPI app.", "If you already paid, call 1930 and your bank now."],
        "hi": ["स्कैन, मंज़ूरी या PIN न डालें।", "अपने UPI ऐप में अनुरोध को अस्वीकार (Decline) करें।", "अगर पैसे जा चुके हैं, तो तुरंत 1930 और अपने बैंक को कॉल करें।"],
        "bn": ["স্ক্যান, অনুমোদন বা PIN দেবেন না।", "UPI অ্যাপে অনুরোধটা বাতিল (Decline) করুন।", "টাকা চলে গিয়ে থাকলে এখনই 1930 আর আপনার ব্যাংকে ফোন করুন।"],
    },
    "caution": {
        "en": ["Pay only if you meant to pay this person this amount.", "Check the name your UPI app shows before entering the PIN.", "If anything feels off, stop and ask someone you trust."],
        "hi": ["तभी भुगतान करें जब आप सच में इसी व्यक्ति को यही रकम देना चाहते हों।", "PIN डालने से पहले UPI ऐप में दिखाया गया नाम जाँचें।", "कुछ भी अजीब लगे तो रुकें और किसी भरोसेमंद व्यक्ति से पूछें।"],
        "bn": ["শুধু তখনই দিন যদি সত্যিই এই মানুষকে এই টাকা দিতে চান।", "PIN দেওয়ার আগে UPI অ্যাপে দেখানো নাম মিলিয়ে নিন।", "কিছু অস্বাভাবিক লাগলে থামুন, ভরসার কাউকে জিজ্ঞেস করুন।"],
    },
    "info": {
        "en": ["Open your bank app yourself and check the balance.", "Don't send any money back because someone asks.", "If they insist, tell them to contact their own bank."],
        "hi": ["खुद अपना बैंक ऐप खोलकर बैलेंस देखें।", "किसी के कहने पर कोई पैसा वापस न भेजें।", "अगर वे ज़िद करें, तो उन्हें अपने बैंक से संपर्क करने को कहें।"],
        "bn": ["নিজে ব্যাংকের অ্যাপ খুলে ব্যালান্স দেখুন।", "কেউ বললেই টাকা ফেরত পাঠাবেন না।", "জোর করলে তাঁকে নিজের ব্যাংকে যোগাযোগ করতে বলুন।"],
    },
    "link": {
        "en": ["Don't open the website from the QR.", "If it claims to be a company, type the company's address yourself.", "Never enter card details, OTP or PIN on a page opened from a QR."],
        "hi": ["QR से खुलने वाली वेबसाइट न खोलें।", "अगर यह किसी कंपनी का होने का दावा करे, तो कंपनी का पता खुद टाइप करें।", "QR से खुले पेज पर कभी कार्ड, OTP या PIN न डालें।"],
        "bn": ["QR থেকে ওয়েবসাইট খুলবেন না।", "কোনো কোম্পানির বলে দাবি করলে ঠিকানাটা নিজে টাইপ করুন।", "QR থেকে খোলা পেজে কখনো কার্ড, OTP বা PIN দেবেন না।"],
    },
}


def _t(key: str, lang: str, **kw) -> str:
    return S[key][lang].format(**kw)


# --------------------------------------------------------------------------- #
# QR + URI
# --------------------------------------------------------------------------- #
def decode_qr(image: bytes) -> list[str]:
    """Return the text inside any QR codes in the image (empty list if none, or if OpenCV is missing)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    arr = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return []
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        detectors.append(cv2.QRCodeDetectorAruco())
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    found: list[str] = []
    # OpenCV's detector is sensitive to module size, so try a few scales and both detectors.
    for base in (gray, binary):
        for scale in (1.0, 1.5, 0.75, 2.0, 0.5):
            img = base if scale == 1.0 else cv2.resize(
                base, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST)
            if min(img.shape[:2]) < 60 or max(img.shape[:2]) > 4000:
                continue
            for det in detectors:
                try:
                    text, points, _ = det.detectAndDecode(img)
                except cv2.error:
                    continue
                if text:
                    found.append(text)
                    break
            if found:
                return list(dict.fromkeys(found))
    return list(dict.fromkeys(found))


def parse_upi_uri(uri: str) -> dict | None:
    """Parse upi://pay?pa=..&pn=..&am=.. (and upi://collect). Returns None if it isn't a UPI link."""
    uri = (uri or "").strip()
    if not uri.lower().startswith("upi://"):
        return None
    parsed = urlparse(uri)
    q = {k.lower(): unquote(v[0]).strip() for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    vpa = q.get("pa", "")
    amount = None
    try:
        if q.get("am"):
            amount = round(float(q["am"]), 2)
    except ValueError:
        amount = None
    return {
        "action": (parsed.netloc or parsed.path.strip("/")).lower() or "pay",
        "vpa": vpa,
        "name": q.get("pn", ""),
        "amount": amount,
        "currency": q.get("cu", "INR") or "INR",
        "note": q.get("tn", ""),
        "merchant_code": q.get("mc", ""),
        "reference": q.get("tr", ""),
    }


def handle_info(vpa: str) -> dict:
    user, _, handle = (vpa or "").partition("@")
    handle = handle.lower()
    return {"handle": handle, "app": HANDLES.get(handle), "is_phone": bool(re.fullmatch(r"(\+?91)?[6-9]\d{9}", user))}


def _fmt_amount(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        value = float(value.replace(",", ""))
    return "₹" + (f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}")


def _claimed_brand(text: str) -> str | None:
    low = text.lower()
    for b in BRANDS:
        if any(re.search(r"\b" + re.escape(k) + r"\b", low) for k in b["keywords"]):
            return b["name"]
    return None


# --------------------------------------------------------------------------- #
# Main check
# --------------------------------------------------------------------------- #
def check(text: str = "", qr_payloads: list | tuple = (), lang: str = "en") -> dict:
    lang = lang if lang in LANGS else "en"
    text = (text or "").strip()
    flags: list[dict] = []

    def flag(key, **kw):
        if any(f["key"] == key for f in flags):
            return
        sev, strings = FLAGS[key]
        title, detail = strings[lang]
        flags.append({"key": key, "severity": sev, "title": title.format(**kw), "detail": detail.format(**kw)})

    upi = next((u for u in (parse_upi_uri(p) for p in qr_payloads) if u), None)
    if upi is None:  # a upi:// link pasted as text counts too
        m = re.search(r"upi://[^\s\"'<>]+", text, re.I)
        upi = parse_upi_uri(m.group(0)) if m else None
    other_qr = [p for p in qr_payloads if not p.lower().startswith("upi://")]

    vpa = upi["vpa"] if upi else ""
    if not vpa:
        m = next((m for m in VPA_RE.finditer(text) if not EMAIL_TLDS.match(m.group(2)) and "." not in m.group(2)), None)
        vpa = m.group(0) if m else ""
    name = (upi or {}).get("name", "")
    amount_val = (upi or {}).get("amount")
    if amount_val is None:
        m = AMOUNT_RE.search(text)
        amount_val = float(m.group(1).replace(",", "")) if m else None
    amount = _fmt_amount(amount_val)

    cues = {k: bool(p.search(text)) for k, p in CUES.items()}
    if not name:
        m = REQUESTER_RE.search(text)
        name = m.group(1).strip() if m else ""
    payee = (f"{name} ({vpa})" if name and vpa else name or vpa) or _t("someone", lang)

    # What kind of thing is this?
    if upi:
        kind = "collect" if upi["action"] == "collect" else "qr"
    elif cues["collect"]:
        kind = "collect"
    elif other_qr:
        kind = "link_qr"
    elif cues["mistake"]:
        kind = "mistake"
    elif cues["credited_sms"] and not (cues["pin"] or cues["collect"]):
        kind = "credited"
    elif cues["pin"] or cues["receive_trick"] or cues["remote"]:
        kind = "pin_text"
    elif vpa:
        kind = "pay_text"
    else:
        kind = "none"

    for key in ("receive_trick", "pin", "refund_bait", "mistake", "urgency", "remote"):
        if cues[key]:
            flag(key)
    if kind in ("collect",):
        flag("collect")
    if upi and upi.get("amount") is not None:
        flag("prefilled", amount=amount)

    link = None
    if kind == "link_qr":
        payload = other_qr[0]
        if re.match(r"https?://|www\.", payload, re.I):
            link = analyze_url(payload if payload.lower().startswith("http") else "http://" + payload)
            if link["points"] >= 15:
                flag("risky_link", why="; ".join(link["flags"][:2]))

    info = handle_info(vpa) if vpa else None
    if info:
        if info["is_phone"]:
            flag("personal_vpa")
        elif not info["app"]:
            flag("unknown_handle", handle=info["handle"])
    brand = _claimed_brand(text + " " + ((upi or {}).get("note") or ""))
    if brand in PAYMENT_APPS:  # "on Google Pay" names the app being used, not who is asking
        brand = None
    if brand and (name or vpa) and kind in ("qr", "collect", "pin_text", "pay_text"):
        target = (name + " " + vpa).lower()
        tokens = next(b["tokens"] + [k.replace(" ", "") for k in b["keywords"]] for b in BRANDS if b["name"] == brand)
        if not any(t in target.replace(" ", "") for t in tokens) and not (upi or {}).get("merchant_code"):
            flag("brand_mismatch", brand=brand, name=name or vpa)

    # Plain-language truth and verdict
    amt_or_any = amount or (_t("any_amount", lang) if kind in ("qr", "pay_text") else _t("the_amount", lang))
    if kind == "qr":
        truth = _t("truth_qr", lang, amount=amt_or_any, payee=payee)
    elif kind == "collect":
        truth = _t("truth_collect", lang, amount=amt_or_any, payee=payee)
    elif kind == "credited":
        truth = _t("truth_credited", lang)
    elif kind == "mistake":
        truth = _t("truth_mistake", lang)
    elif kind == "pay_text":
        truth = _t("truth_pay", lang, amount=amt_or_any, payee=payee)
    elif kind == "pin_text":
        truth = _t("truth_pin", lang)
    elif kind == "link_qr":
        domain = (link or {}).get("domain") or other_qr[0][:60]
        truth = _t("truth_link", lang, domain=domain)
    else:
        truth = _t("truth_none", lang)

    trick = cues["receive_trick"] or cues["mistake"] or cues["remote"] or any(f["key"] == "brand_mismatch" for f in flags) \
        or (cues["refund_bait"] and kind in ("qr", "collect", "pin_text", "pay_text"))
    if kind == "none":
        verdict = "none"
    elif kind == "credited":
        verdict = "danger" if cues["mistake"] else "info"
    elif kind == "mistake":
        verdict = "danger"
    elif kind == "link_qr":
        verdict = "danger" if flags else "caution"
    elif trick or (kind == "pin_text" and cues["pin"]):
        verdict = "danger"
    else:
        verdict = "caution"

    head_key = {"danger": "head_danger", "caution": "head_caution", "info": "head_info", "none": "head_none"}[verdict]
    if kind == "link_qr" and verdict == "caution":
        head_key = "head_link"
    steps_key = "link" if kind == "link_qr" else ("info" if verdict == "info" or kind == "mistake" else ("caution" if verdict == "caution" else "danger"))

    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: order[f["severity"]])
    return {
        "kind": kind,
        "verdict": verdict,
        "headline": _t(head_key, lang),
        "truth": truth,
        "direction": "out" if kind in ("qr", "collect", "pin_text", "pay_text", "mistake") else ("in" if kind == "credited" else None),
        "amount": amount or None,
        "payee": {"vpa": vpa or None, "name": name or None, "app": (info or {}).get("app"),
                  "is_personal": bool(info and info["is_phone"]), "merchant": bool((upi or {}).get("merchant_code"))} if (vpa or name) else None,
        "note_on_qr": (upi or {}).get("note") or None,
        "flags": flags,
        "steps": STEPS[steps_key][lang] if verdict != "none" else [],
        "qr_found": bool(qr_payloads),
        "qr_text": [p[:200] for p in qr_payloads][:3],
        "language": lang,
    }
