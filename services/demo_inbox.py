"""A pretend mailbox with realistic emails, for demos and testing without a Google account.

It behaves like GmailClient (same methods), but everything happens in memory.
All senders, numbers and domains are made up.
"""
import time

_MAILS = [
    {
        "id": "demo-bank", "from_name": "SBI Alerts", "from_email": "alerts.sbi.update@gmail.com",
        "subject": "URGENT: Your account will be blocked today",
        "body": "Dear Customer,\n\nYour SBI account will be BLOCKED within 30 minutes due to incomplete KYC.\n\n"
                "Verify immediately and enter your account number and OTP to avoid suspension.\n\nSBI Support Team",
        "links": ["http://sbi-kyc-verify.xyz/login?session=88a1"],
        "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "age": 0.3,
    },
    {
        "id": "demo-netflix", "from_name": "Netflix", "from_email": "billing@netflix-account-help.com",
        "subject": "Your membership is on hold",
        "body": "Hi,\n\nWe couldn't process your last payment, so your Netflix membership is on hold.\n\n"
                "Update your card details within 24 hours to avoid cancellation.\n\nThe Netflix Team",
        "links": ["https://netflix-billing-update.top/account/payment"],
        "auth": {"spf": "fail", "dkim": "fail", "dmarc": "fail"}, "age": 1.5,
    },
    {
        "id": "demo-job", "from_name": "HR Team Amazon", "from_email": "amazon.hr.jobs2026@outlook.com",
        "subject": "Selected: Work from home part-time job (Rs 8,000/day)",
        "body": "Hello!\n\nWe are hiring for Amazon work-from-home part-time job. Earn Rs 3,000-8,000 per day by liking "
                "YouTube videos. No experience needed.\n\nPay a refundable registration fee of Rs 499 to confirm your "
                "seat. Contact HR on WhatsApp: +91 98765 43210. Limited seats, reply today!",
        "links": [], "auth": {"spf": "pass", "dkim": "pass", "dmarc": "none"}, "age": 3,
    },
    {
        "id": "demo-scholarship", "from_name": "National Scholarship Cell", "from_email": "nsp.cell@nsp-scholarship-portal.in.net",
        "subject": "Scholarship of Rs 50,000 approved - action required",
        "body": "Dear Student,\n\nYou are selected for the National Merit Scholarship 2026 of Rs 50,000. To release the "
                "amount, pay a verification fee of Rs 1,200 and share your bank account number, IFSC and the OTP you "
                "receive.\n\nApply before midnight.",
        "links": ["https://nsp-scholarship-portal.in.net/apply"],
        "auth": {"spf": "pass", "dkim": None, "dmarc": "none"}, "age": 6,
    },
    {
        "id": "demo-amazon", "from_name": "Amazon.in", "from_email": "shipment-tracking@amazon.in",
        "subject": "Your Amazon.in order has shipped",
        "body": "Hello Binayak,\n\nYour order #402-7781234 has shipped and will arrive on Thursday.\n\n"
                "Track your package in Your Orders on the Amazon app.",
        "links": ["https://www.amazon.in/gp/your-account/order-history"],
        "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "list_unsubscribe": False, "age": 8,
    },
    {
        "id": "demo-hdfc-otp", "from_name": "HDFC Bank", "from_email": "alerts@hdfcbank.com",
        "subject": "OTP for your NetBanking login",
        "body": "Your OTP for NetBanking login is 482910. It is valid for 10 minutes.\n\nNever share your OTP with "
                "anyone. HDFC Bank will never ask for your OTP, PIN or password.",
        "links": [], "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "age": 20,
    },
    {
        "id": "demo-college", "from_name": "Dept. of Computer Applications", "from_email": "hod.ca@college.edu.in",
        "subject": "CA2 internal assessment schedule",
        "body": "Dear students,\n\nThe CA2 internal assessment for BCA Semester V will be held from 10 November. "
                "The detailed timetable is on the notice board and the official college website.\n\nHOD, CA",
        "links": [], "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "age": 26,
    },
    {
        "id": "demo-newsletter", "from_name": "DEV Community", "from_email": "yo@dev.to",
        "subject": "Hacktoberfest 2026 challenges are live",
        "body": "This week on DEV: the Hacktoberfest Weekend Challenge is open. Build something with open-source AI "
                "and share it with the community.",
        "links": ["https://dev.to/challenges?utm_source=newsletter&utm_campaign=hf26&u=8f2a91c3d4e5f6a7b8c9d0e1f2a3"],
        "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "list_unsubscribe": True, "age": 30,
    },
    {
        "id": "demo-prize", "from_name": "KBC Lottery Department", "from_email": "kbc.lucky.draw@yahoo.com",
        "subject": "CONGRATULATIONS!!! You won Rs 25,00,000",
        "body": "CONGRATULATIONS!!! Your email has won Rs 25,00,000 in the KBC Lucky Draw 2026. To claim your prize, pay "
                "a processing fee of Rs 4,999 to UPI ID kbcprize.claim@ybl and send your Aadhaar and bank details on "
                "WhatsApp +44 7700 900123. Offer expires today.",
        "links": [], "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "age": 40,
    },
    {
        "id": "demo-electricity", "from_name": "बिजली विभाग", "from_email": "bijli.vibhag.office@gmail.com",
        "subject": "बिजली कनेक्शन काटने की सूचना",
        "body": "प्रिय ग्राहक, आपका बिजली कनेक्शन आज रात 9:30 बजे काट दिया जाएगा क्योंकि पिछला बिल अपडेट नहीं हुआ है। "
                "तुरंत बिजली अधिकारी से 9876543210 पर संपर्क करें।",
        "links": [], "auth": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}, "age": 50,
    },
]


class DemoMailbox:
    def __init__(self):
        self.reset()

    def reset(self):
        self.location = {m["id"]: "inbox" for m in _MAILS}
        self.filters = {}  # filter_id -> sender
        self._n = 0

    def profile(self):
        return {"emailAddress": "demo-inbox@scamshield.local"}

    def list_messages(self, limit=25, query=None):
        blocked = set(self.filters.values())
        return [m["id"] for m in _MAILS
                if self.location[m["id"]] == "inbox" and m["from_email"] not in blocked][:limit]

    def get_message(self, message_id):
        m = next((x for x in _MAILS if x["id"] == message_id), None)
        if not m:
            raise KeyError(message_id)
        ts = int(time.time() - m["age"] * 3600)
        return {
            "id": m["id"], "from_name": m["from_name"], "from_email": m["from_email"], "subject": m["subject"],
            "date": time.strftime("%a, %d %b %Y %H:%M", time.localtime(ts)), "timestamp": ts,
            "snippet": m["body"].replace("\n", " ")[:160], "body": m["body"], "links": m["links"],
            "auth": m["auth"], "list_unsubscribe": m.get("list_unsubscribe", False), "labels": ["INBOX"],
        }

    def move_to_spam(self, message_id):
        self.location[message_id] = "spam"

    def restore_to_inbox(self, message_id):
        self.location[message_id] = "inbox"

    def trash(self, message_id):
        self.location[message_id] = "trash"

    def untrash(self, message_id):
        self.location[message_id] = "inbox"

    def block_sender(self, address):
        self._n += 1
        fid = f"demo-filter-{self._n}"
        self.filters[fid] = address.lower()
        return fid

    def unblock_sender(self, filter_id):
        self.filters.pop(filter_id, None)
