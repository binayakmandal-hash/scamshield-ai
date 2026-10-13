"""Scam script tracker.

Most scams in India follow a script: the same steps, in the same order, whatever the wording.
This module holds a small library of those scripts and matches a whole conversation (for example a
WhatsApp chat export) against them. It tells you which script the conversation looks like, how far
along it is, and what the scammer usually asks for next, so you can stop before that step.

The matcher is rule-based and deterministic: every step it marks as "seen" is backed by a quote from
the chat. The AI model (when available) can re-rank the result, but its answer is only accepted when
its quotes are found in the chat and its script and step exist in this library.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# The library
# --------------------------------------------------------------------------- #


@dataclass
class Step:
    title: str
    what_happens: str
    cues: list[str]
    next_warning: str = ""  # shown when this is the NEXT step the scammer will try


@dataclass
class Script:
    id: str
    name: str
    summary: str
    steps: list[Step]
    advice: str
    patterns: list[re.Pattern] = field(default_factory=list, repr=False)


MONEY = r"(?:₹|rs\.?|inr|rupees?)\s?\d[\d,]*"

SCRIPTS: list[Script] = [
    Script(
        id="task_scam",
        name="Part-time task scam",
        summary="A 'job' paying you to like videos or rate hotels. Small payouts build trust, then you're asked to deposit money to unlock bigger tasks, and the money never comes back.",
        steps=[
            Step("An easy job offer", "Someone offers easy money for simple online tasks.",
                 [r"part[- ]?time", r"work from home", r"earn " + MONEY, r"(daily|per day) (income|earning|salary)",
                  r"simple (online )?tasks?", r"like (and|&) (subscribe|follow)", r"(rate|review) (hotels?|products?|movies?|restaurants?)",
                  r"youtube (likes|videos?)", r"google (maps )?reviews?", r"ghar baithe", r"घर बैठे"]),
            Step("A small first payment", "They pay you a little for the first tasks so you trust them.",
                 [r"(paid|sent|credited) (you )?" + MONEY, r"(received|got) (your )?(reward|commission|payment)",
                  r"commission (credited|received)", r"first (3 )?tasks? (done|completed?)", r"check your (bank )?account"],
                 "They'll pay you a small amount so the job feels real."),
            Step("Moved to a group with 'special tasks'", "You're added to a Telegram group or app with 'prepaid' or 'merchant' tasks.",
                 [r"telegram", r"t\.me/", r"join (our|the|this) (group|channel)", r"receptionist", r"mentor",
                  r"(prepaid|merchant|vip|combination|bonus) tasks?", r"task (app|platform|website)"],
                 "They'll move you to a Telegram group and offer 'prepaid tasks' that need your own money."),
            Step("Deposit to unlock earnings", "You're told to deposit or 'recharge' money to continue or to unlock what you've earned.",
                 [r"deposit", r"recharge", r"top[- ]?up", r"(invest|pay) " + MONEY, r"to (unlock|continue|complete) (the )?(task|level|earnings?)",
                  r"negative balance", r"to withdraw (your )?(earnings|commission|profit)"],
                 "They'll ask you to deposit money to unlock your earnings. This is where the loss starts."),
            Step("More fees to withdraw", "Your 'earnings' are stuck until you pay taxes, fees or penalties, again and again.",
                 [r"(tax|fee|charges?|penalty) (to|before) withdraw", r"account (is )?(frozen|locked)", r"credit score",
                  r"unfreeze", r"pay (again|one more time)", r"one more task", r"(gst|income tax) (on|for) (your )?(earnings|profit)"],
                 "They'll say your money is stuck and ask for a 'tax' or 'fee' to withdraw. It never ends."),
        ],
        advice="Stop paying. No real job asks you to pay to get paid. Report the numbers and group at cybercrime.gov.in or call 1930.",
    ),
    Script(
        id="kyc_expiry",
        name="Fake KYC or account block",
        summary="A message claims your bank account, SIM or wallet will be blocked unless you update KYC through their link, then the link steals your card details or OTP.",
        steps=[
            Step("A scare about your account", "You're told your KYC has expired or your account will be blocked.",
                 [r"kyc (has )?(expired|pending|update|incomplete)", r"account (will be |is )?(blocked|suspended|deactivated|closed)",
                  r"pan (card )?(not )?(linked|update)", r"sim (card )?(will be )?(blocked|deactivated)", r"wallet (will be )?(blocked|suspended)"]),
            Step("Rushed to a link or app", "You're pushed to click a link or install an app quickly.",
                 [r"https?://", r"\bclick\b", r"download", r"\.apk\b", r"update (now|immediately|today)", r"within \d+ (minutes?|mins?|hours?)",
                  r"(before|by) (today|tonight)"],
                 "They'll send a link or an app and tell you to update 'now'."),
            Step("Asked for secret details", "The page or caller asks for your card number, OTP, PIN or net banking login.",
                 [r"\botp\b", r"card (number|details|no)", r"\bcvv\b", r"\bpin\b", r"net ?banking (password|id|login)",
                  r"customer id", r"aadhaar (number|otp)"],
                 "They'll ask for your OTP or card details to 'verify' you. Never share them."),
            Step("Money is taken", "Money is debited using the details you shared.",
                 [MONEY + r" (has been |was )?(debited|deducted|withdrawn)", r"(debited|deducted) from (your )?(a/c|account)", r"transaction (of|for) " + MONEY],
                 "Next, money is taken from your account using those details."),
        ],
        advice="Don't click the link. Banks never ask for an OTP, PIN or card number by message. Check directly with your bank using the number on your card or its official app.",
    ),
    Script(
        id="digital_arrest",
        name="Digital arrest",
        summary="Fake police, CBI or customs officers say you're linked to a crime, keep you on a video call for hours, and make you 'transfer money for verification'. Real police never arrest anyone on a video call.",
        steps=[
            Step("A call from 'officials'", "Someone claims to be from police, CBI, ED, customs, TRAI or a courier company.",
                 [r"\bcbi\b", r"enforcement directorate", r"\bed officer", r"\bpolice\b", r"customs", r"narcotics", r"\bncb\b", r"\btrai\b",
                  r"cyber (crime|cell)", r"fedex", r"courier", r"parcel"]),
            Step("A serious accusation", "You're told your Aadhaar, number or parcel is linked to drugs, money laundering or a case.",
                 [r"drugs?", r"money laundering", r"illegal", r"aadhaar (is |was )?(used|linked|misused)", r"case (is )?(registered|filed)",
                  r"\bfir\b", r"(arrest )?warrant", r"hawala", r"(number|sim) (will be )?(blocked|disconnected) in 2 hours"],
                 "They'll accuse you of a crime, such as drugs in a parcel or money laundering through your Aadhaar."),
            Step("Kept alone on a video call", "You're told to stay on video, not to tell anyone, and that you're under 'digital arrest'.",
                 [r"(stay|remain|be) on (the )?(video|call|skype|camera)", r"don'?t (tell|inform|contact) (anyone|your family|anybody)",
                  r"confidential", r"national secret", r"\bskype\b", r"video call", r"don'?t (disconnect|cut the call)", r"digital arrest",
                  r"under (surveillance|investigation)", r"किसी को मत बताना"],
                 "They'll keep you on a video call and tell you not to tell anyone. That isolation is the key to the scam."),
            Step("Pay to 'clear your name'", "You're told to move your savings to a 'safe RBI account' for verification, with a promise it'll be returned.",
                 [r"(verification|safe|secure|rbi|government) account", r"transfer (your |all )?(money|funds|savings)", r"refundable",
                  r"clearance (fee|amount)", r"(break|liquidate) (your )?(fd|fixed deposits?)", r"will be (returned|refunded) (after|once)"],
                 "They'll ask you to transfer your savings to a 'safe RBI account' to 'verify' it. That money is gone."),
        ],
        advice="Hang up. Police, CBI and customs never investigate or arrest anyone on a video call, and never ask you to transfer money. Tell a family member right away and call 1930.",
    ),
    Script(
        id="investment",
        name="Fake trading or investment group",
        summary="A WhatsApp or Telegram 'stock tips' group shows huge profits, gets you onto a fake trading app, and blocks withdrawals until you pay more.",
        steps=[
            Step("An invite to a tips group", "You're added to a group promising stock tips, IPOs or crypto profits.",
                 [r"stock (market )?tips", r"trading (group|tips|class)", r"\bipo\b", r"crypto", r"guaranteed (returns?|profit)",
                  r"\d+ ?% (returns?|profit)", r"vip (group|members?)", r"sebi registered"]),
            Step("Proof of big profits", "Members post screenshots of huge profits to make it look real.",
                 [r"(made|earned|booked) (a )?(profit|" + MONEY + ")", r"profit of " + MONEY, r"returns? (credited|received)",
                  r"(see|check) (these )?screenshots?", r"thank(s| you) (sir|madam|teacher)"],
                 "They'll show screenshots of other members' big profits."),
            Step("Install their app and deposit", "You're told to register on their platform or app and deposit money.",
                 [r"download (the |our )?app", r"(register|sign up) on", r"\.apk\b", r"institutional (account|trading)",
                  r"(deposit|invest) " + MONEY, r"minimum (investment|deposit)", r"trading platform"],
                 "They'll ask you to install their own app and deposit money."),
            Step("Withdrawals blocked", "Your 'profits' can't be withdrawn until you pay a tax, fee or 'margin'.",
                 [r"withdraw(al)? (fee|tax|charges?)", r"account (is )?(frozen|locked)", r"pay (the )?(tax|fee|commission) (to|before) withdraw",
                  r"\bmargin\b", r"insurance fee", r"service fee"],
                 "When you try to withdraw, they'll demand a 'tax' or 'fee' first."),
        ],
        advice="Don't deposit more. Only use SEBI-registered brokers' official apps from the Play Store or App Store. Report the group at cybercrime.gov.in.",
    ),
    Script(
        id="job_fee",
        name="Fake job offer with a fee",
        summary="An offer letter for a job you barely applied for, followed by a 'registration' or 'refundable deposit' fee.",
        steps=[
            Step("You've been 'selected'", "You're told you're selected or shortlisted, often without a real interview.",
                 [r"(selected|shortlisted) for", r"job offer", r"offer letter", r"\bhiring\b", r"vacancy", r"no interview",
                  r"joining (letter|date)"]),
            Step("Asked to pay a fee", "You're asked for a registration, training, security or document fee.",
                 [r"(registration|training|security|processing|documentation|verification) (fee|charge|deposit)",
                  r"refundable (fee|deposit|amount)", r"pay " + MONEY, r"(laptop|kit|uniform) (charge|fee)"],
                 "They'll ask for a 'registration' or 'refundable' fee to confirm the job."),
            Step("More fees, then silence", "More charges appear, then the 'company' stops replying.",
                 [r"(second|next) (installment|payment)", r"insurance (fee|charge)", r"one more (fee|payment)",
                  r"(blocked|not responding|no reply)"],
                 "After the first payment, more charges will follow."),
        ],
        advice="Real employers never charge you to get a job. Check the company's official careers page and email domain before paying anything.",
    ),
    Script(
        id="parcel",
        name="Courier or parcel fee",
        summary="A delivery 'failed' and needs a small redelivery fee or an address update through a link, which steals your card details.",
        steps=[
            Step("A parcel problem", "Your parcel is held, returned or needs an address update.",
                 [r"parcel (is )?(held|stuck|on hold|returned|seized)", r"delivery (failed|attempt|unsuccessful)", r"address (is )?(incomplete|wrong|update)",
                  r"india ?post", r"\bdhl\b", r"blue ?dart", r"\bdtdc\b"]),
            Step("A small fee or a link", "You're asked to pay a tiny fee or update details through a link.",
                 [r"(redelivery|re-delivery|delivery|customs) (fee|charge)", r"pay " + MONEY, r"https?://", r"\bclick\b"],
                 "They'll ask for a tiny 'redelivery fee' through a link."),
            Step("Card details or OTP", "The page asks for your full card details or an OTP.",
                 [r"card (number|details)", r"\botp\b", r"\bcvv\b", r"upi pin"],
                 "The payment page will ask for your card details or OTP, and take much more than the fee."),
        ],
        advice="Check delivery status only on the courier's official website or app, by typing the address yourself.",
    ),
    Script(
        id="electricity",
        name="Electricity disconnection",
        summary="A message says your power will be cut tonight because the bill wasn't updated. The 'officer' gets you to install a remote-access app or pay through a link.",
        steps=[
            Step("Power will be cut tonight", "You're told your electricity will be disconnected tonight.",
                 [r"(electricity|power|light|bijli) (connection|supply)? ?(will be )?(cut|disconnected|disconnect)",
                  r"(bill|electricity bill) (is )?(not )?(updated|paid)", r"tonight at \d", r"\b9[:.]30\b", r"wbsedcl|cesc|bses|msedcl|tneb|bescom"]),
            Step("Call the 'officer'", "You're told to call a personal mobile number.",
                 [r"(call|contact) (our |the |this )?(electricity )?(officer|number|helpline)", r"immediately call", r"\b[6-9]\d{9}\b"],
                 "They'll ask you to call an 'electricity officer' on a personal mobile number."),
            Step("Install an app", "The 'officer' asks you to install an app like AnyDesk to 'update' the bill.",
                 [r"anydesk", r"teamviewer", r"quick ?support", r"rustdesk", r"screen ?shar", r"\.apk\b", r"download (this |the )?app"],
                 "They'll ask you to install a screen-sharing app like AnyDesk so they can 'help'."),
            Step("Pay a small amount", "You're asked to pay ₹10 or so, while they watch your screen and take your details.",
                 [r"pay " + MONEY, r"(₹|rs\.?) ?(10|11|5)\b", r"\botp\b", r"upi pin"],
                 "They'll ask you to pay a tiny amount while watching your screen, then empty your account."),
        ],
        advice="Electricity boards never message you from personal numbers or ask you to install apps. Check your bill only on the board's official website or app.",
    ),
    Script(
        id="prize",
        name="Prize, lottery or KBC",
        summary="You've 'won' a lottery, KBC prize or gift, but must pay tax or a fee first.",
        steps=[
            Step("You've won", "You're told you've won a lottery, lucky draw, KBC prize or gift.",
                 [r"\bwon\b", r"winner", r"lottery", r"lucky draw", r"\bkbc\b", r"kaun banega", r"prize", MONEY + r" ?lakh", r"\d+ ?lakh"]),
            Step("Pay to claim", "You're asked for a tax, GST or processing fee to release the prize.",
                 [r"(processing|registration|gst|tax|clearance|transfer) (fee|charge)", r"pay " + MONEY + " to (claim|receive|release)"],
                 "They'll ask for a 'tax' or 'processing fee' to release your prize."),
            Step("More fees", "New charges keep appearing: RBI clearance, income tax, delivery.",
                 [r"\brbi\b", r"income tax", r"(delivery|courier) charge", r"one more (fee|charge)", r"(pay|send) again"],
                 "Once you pay, new 'charges' will keep coming."),
        ],
        advice="You can't win a contest you never entered. Real prizes never need a fee first.",
    ),
    Script(
        id="marketplace_qr",
        name="Buyer sends a QR or payment request",
        summary="A 'buyer' (often claiming to be in the army) wants your item and sends a QR code or payment request 'so you can receive money'. Scanning or approving it sends your money to them.",
        steps=[
            Step("An eager buyer", "Someone wants to buy what you're selling without seeing it, often saying they're in the army.",
                 [r"\bolx\b", r"marketplace", r"(interested in|want to buy) your", r"army (officer|personnel|man)", r"\bcisf\b",
                  r"(i'?m|i am) (being )?transferred", r"without (seeing|checking)"]),
            Step("A QR or request 'to pay you'", "They send a QR code or a UPI collect request and say it's so you can receive the money.",
                 [r"scan (this|the) qr", r"qr code", r"collect request", r"request(ed)? (money|" + MONEY + ")",
                  r"to receive (the )?(money|payment)", r"enter (your )?(upi )?pin to (receive|get)"],
                 "They'll send a QR code or a payment request and say you'll RECEIVE money by approving it. You won't. It sends yours."),
            Step("'Sent by mistake', scan again", "After your money goes, they claim a mistake and ask you to scan again to get a refund.",
                 [r"(sent|paid) by mistake", r"\brefund\b", r"scan (it )?again", r"(pay|send) (double|again)", r"wrong amount"],
                 "They'll claim it was a mistake and ask you to scan again for a 'refund'."),
        ],
        advice="You never scan a QR or enter a UPI PIN to receive money. Only accept payments that arrive without you doing anything.",
    ),
]

for _s in SCRIPTS:
    _s.patterns = [[re.compile(c, re.I) for c in step.cues] for step in _s.steps]


def library() -> list[dict]:
    """The library as plain data, for the AI prompt and the UI."""
    return [{"id": s.id, "name": s.name, "steps": [st.title for st in s.steps]} for s in SCRIPTS]


def get(script_id: str) -> Script | None:
    return next((s for s in SCRIPTS if s.id == script_id), None)


# --------------------------------------------------------------------------- #
# Parsing a chat
# --------------------------------------------------------------------------- #
# Android:  12/10/26, 9:14 pm - Ravi: hello
# iOS:      [12/10/26, 9:14:03 PM] Ravi: hello
_LINE = re.compile(
    r"^\[?(?P<date>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s+(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?\s?(?:[ap]\.?m\.?)?)\]?\s*(?:-\s*)?"
    r"(?P<who>[^:]{1,40}):\s(?P<text>.*)$", re.I)
_SYSTEM = re.compile(r"(messages and calls are end-to-end encrypted|<media omitted>|this message was deleted|created group|added you|joined using)", re.I)


def parse_chat(raw: str) -> list[dict]:
    """Split a pasted chat or WhatsApp export into messages: [{who, text}]. Plain text becomes one message per line."""
    lines = [ln.rstrip() for ln in (raw or "").replace("\r", "").split("\n")]
    messages: list[dict] = []
    matched_any = False
    for ln in lines:
        m = _LINE.match(ln.strip().lstrip("‎"))
        if m:
            matched_any = True
            text = m.group("text").strip()
            if text and not _SYSTEM.search(text):
                messages.append({"who": m.group("who").strip(), "text": text})
        elif ln.strip():
            if matched_any and messages:
                messages[-1]["text"] += " " + ln.strip()  # continuation of a multi-line message
            elif not matched_any:
                who, sep, text = ln.partition(":")
                if sep and 0 < len(who) <= 25 and text.strip():
                    messages.append({"who": who.strip(), "text": text.strip()})
                else:
                    messages.append({"who": "", "text": ln.strip()})
    return messages


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def _quote(text: str, m: re.Match, width: int = 70) -> str:
    start = max(0, m.start() - 25)
    end = min(len(text), m.end() + 35)
    q = text[start:end].strip()
    return ("…" if start > 0 else "") + q[:width] + ("…" if end < len(text) or len(q) > width else "")


def _score(script: Script, messages: list[dict]) -> dict:
    hits = []  # per step: list of {msg, who, quote, cue}
    for patterns in script.patterns:
        found = []
        for i, msg in enumerate(messages):
            for p in patterns:
                m = p.search(msg["text"])
                if m:
                    found.append({"msg": i, "who": msg["who"], "quote": _quote(msg["text"], m), "cue": m.group(0)})
                    break
        hits.append(found)
    seen = [i for i, h in enumerate(hits) if h]
    # Steps that appear in the expected order count fully; out-of-order steps count half.
    order_bonus = 0.0
    last_msg = -1
    for i in seen:
        first = min(h["msg"] for h in hits[i])
        order_bonus += 1.0 if first >= last_msg else 0.5
        last_msg = max(last_msg, first)
    distinct_cues = sum(len({h["cue"].lower() for h in hits[i]}) for i in seen)
    score = order_bonus + 0.15 * min(distinct_cues, 10)
    return {"hits": hits, "seen": seen, "score": round(score, 2)}


def track(raw_chat: str) -> dict:
    """Match a conversation against the script library. Always returns a JSON-friendly dict."""
    messages = parse_chat(raw_chat)
    if not messages:
        return {"matched": False, "messages": 0, "reason": "No messages found. Paste the chat text or upload a WhatsApp export (.txt)."}

    ranked = sorted(((_score(s, messages), s) for s in SCRIPTS), key=lambda x: -x[0]["score"])
    best, script = ranked[0]
    # Need at least two different steps of one script before calling it a match.
    if len(best["seen"]) < 2:
        near = [{"id": s.id, "name": s.name} for r, s in ranked if r["seen"]][:2]
        return {"matched": False, "messages": len(messages), "near": near,
                "reason": "This conversation doesn't clearly follow a known scam script. That isn't proof it's safe: "
                          "never share an OTP or PIN, and never pay to receive money or get a job."}

    current = max(best["seen"])
    steps = []
    for i, st in enumerate(script.steps):
        status = "seen" if i in best["seen"] else ("next" if i == current + 1 else ("skipped" if i < current else "later"))
        if i == current:
            status = "now"
        steps.append({"n": i + 1, "title": st.title, "what_happens": st.what_happens, "status": status,
                      "evidence": [{"who": h["who"], "quote": h["quote"]} for h in best["hits"][i][:2]]})
    nxt = script.steps[current + 1] if current + 1 < len(script.steps) else None
    total_steps = len(script.steps)
    confidence = "high" if len(best["seen"]) >= 3 or (len(best["seen"]) == total_steps) else "medium"
    return {
        "matched": True,
        "engine": "rules",
        "messages": len(messages),
        "script": {"id": script.id, "name": script.name, "summary": script.summary, "advice": script.advice},
        "steps": steps,
        "current_step": current + 1,
        "total_steps": total_steps,
        "next_move": nxt.next_warning if nxt else "This is the last step of the script. If you've paid, act now: call 1930 and your bank.",
        "at_end": nxt is None,
        "confidence": confidence,
        "also_possible": [{"id": s.id, "name": s.name} for r, s in ranked[1:3] if len(r["seen"]) >= 2],
    }


def apply_ai(result: dict, ai: dict, raw_chat: str) -> dict:
    """Accept the AI's view only if it is consistent with the library and quotes the chat word for word."""
    if not isinstance(ai, dict):
        return result
    script = get(str(ai.get("script_id", "")))
    try:
        step = int(ai.get("current_step", 0))
    except (TypeError, ValueError):
        return result
    if not script or not (1 <= step <= len(script.steps)):
        return result
    quotes = [q for q in ai.get("evidence", []) if isinstance(q, str) and len(q) >= 6]
    if not quotes or not all(q.lower() in raw_chat.lower() for q in quotes):
        return result  # unverifiable: keep the rule-based answer
    if result.get("matched") and result["script"]["id"] == script.id:
        result["engine"] = "rules+ai"
        result["ai_note"] = str(ai.get("note", ""))[:300]
        return result
    # The AI found a different, verifiable script. Rebuild the result around it.
    steps = []
    for i, st in enumerate(script.steps):
        status = "seen" if i < step - 1 else ("now" if i == step - 1 else ("next" if i == step else "later"))
        steps.append({"n": i + 1, "title": st.title, "what_happens": st.what_happens, "status": status, "evidence": []})
    steps[step - 1]["evidence"] = [{"who": "", "quote": q[:80]} for q in quotes[:2]]
    nxt = script.steps[step] if step < len(script.steps) else None
    return {
        "matched": True, "engine": "ai", "messages": result.get("messages", 0),
        "script": {"id": script.id, "name": script.name, "summary": script.summary, "advice": script.advice},
        "steps": steps, "current_step": step, "total_steps": len(script.steps),
        "next_move": nxt.next_warning if nxt else "This is the last step of the script. If you've paid, act now: call 1930 and your bank.",
        "at_end": nxt is None, "confidence": "medium", "ai_note": str(ai.get("note", ""))[:300], "also_possible": [],
    }
