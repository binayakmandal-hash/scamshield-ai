"""Tests for the safety tools: chat check, UPI check, call copilot and golden hour. No AI or network needed."""
import io
import json
import os
import re
import tempfile
import unittest
import zipfile

os.environ["AI_PROVIDER"] = "none"
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))

import app as app_module  # noqa: E402
from services import call_tactics, payment_receipt, scam_scripts, upi_check  # noqa: E402

try:
    import cv2  # noqa: F401
    HAS_QR = hasattr(cv2, "QRCodeEncoder")
except ImportError:
    HAS_QR = False

TASK_CHAT = """12/10/26, 9:14 pm - Priya HR: Hello! We are hiring for part-time work from home. Earn Rs 3000 daily by liking YouTube videos.
12/10/26, 9:15 pm - Me: ok
12/10/26, 9:21 pm - Priya HR: First 3 tasks completed! We have sent you Rs 150, check your bank account
12/10/26, 9:30 pm - Priya HR: Now join our Telegram group for prepaid tasks t.me/earn_daily
12/10/26, 9:41 pm - Mentor Rahul: Deposit Rs 1000 to unlock the task and get 30% commission."""


def qr_png(text: str) -> bytes:
    import cv2
    q = cv2.QRCodeEncoder.create().encode(text)
    q = cv2.resize(q, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    q = cv2.copyMakeBorder(q, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    return cv2.imencode(".png", q)[1].tobytes()


class ScamScriptTest(unittest.TestCase):
    def test_parses_android_and_ios_exports(self):
        android = "12/10/26, 9:14 pm - Ravi: hello\nsecond line\n12/10/26, 9:15 pm - Me: hi"
        ios = "[12/10/26, 9:14:03 PM] Ravi: hello\n[12/10/26, 9:15:00 PM] Me: <Media omitted>"
        self.assertEqual(scam_scripts.parse_chat(android), [{"who": "Ravi", "text": "hello second line"}, {"who": "Me", "text": "hi"}])
        self.assertEqual(scam_scripts.parse_chat(ios), [{"who": "Ravi", "text": "hello"}])

    def test_tracks_task_scam_and_predicts_next_step(self):
        r = scam_scripts.track(TASK_CHAT)
        self.assertTrue(r["matched"])
        self.assertEqual(r["script"]["id"], "task_scam")
        self.assertEqual(r["current_step"], 4)
        self.assertEqual([s["status"] for s in r["steps"]], ["seen", "seen", "seen", "now", "next"])
        self.assertIn("tax", r["next_move"])
        # Every seen step is backed by a quote from the chat.
        for step in r["steps"]:
            if step["status"] in ("seen", "now"):
                self.assertTrue(step["evidence"])

    def test_digital_arrest(self):
        chat = ("Officer: This is CBI. A FedEx parcel in your name has drugs.\n"
                "Officer: An FIR is registered. Stay on the video call and don't tell anyone.")
        r = scam_scripts.track(chat)
        self.assertEqual(r["script"]["id"], "digital_arrest")
        self.assertIn("RBI", r["next_move"])

    def test_normal_chat_is_not_matched(self):
        r = scam_scripts.track("Mom: are you coming for dinner?\nMe: yes at 8\nMom: bring milk")
        self.assertFalse(r["matched"])
        self.assertIn("isn't proof", r["reason"])

    def test_empty_chat(self):
        self.assertFalse(scam_scripts.track("   ")["matched"])

    def test_ai_answer_is_only_accepted_with_verbatim_quotes(self):
        base = scam_scripts.track(TASK_CHAT)
        fake = {"script_id": "digital_arrest", "current_step": 2, "evidence": ["this quote is not in the chat"]}
        self.assertEqual(scam_scripts.apply_ai(dict(base), fake, TASK_CHAT)["script"]["id"], "task_scam")
        bad_step = {"script_id": "task_scam", "current_step": 9, "evidence": ["Deposit Rs 1000"]}
        self.assertEqual(scam_scripts.apply_ai(dict(base), bad_step, TASK_CHAT)["engine"], "rules")
        good = {"script_id": "task_scam", "current_step": 4, "evidence": ["Deposit Rs 1000 to unlock the task"], "note": "n"}
        self.assertEqual(scam_scripts.apply_ai(dict(base), good, TASK_CHAT)["engine"], "rules+ai")


class UpiCheckTest(unittest.TestCase):
    def test_parse_uri(self):
        u = upi_check.parse_upi_uri("upi://pay?pa=shop@okaxis&pn=Ram%20Stores&am=250.50&cu=INR&mc=5411")
        self.assertEqual((u["vpa"], u["name"], u["amount"], u["merchant_code"]), ("shop@okaxis", "Ram Stores", 250.5, "5411"))
        self.assertIsNone(upi_check.parse_upi_uri("https://example.com"))

    def test_collect_request_with_receive_trick_is_danger(self):
        r = upi_check.check("Ramesh Kumar has requested Rs 2,000 from you. Approve to receive your cashback.")
        self.assertEqual((r["kind"], r["verdict"], r["direction"]), ("collect", "danger", "out"))
        self.assertIn("Ramesh Kumar", r["truth"])
        self.assertIn("₹2,000", r["truth"])
        self.assertEqual(r["flags"][0]["severity"], "high")

    def test_credited_sms_needs_no_action(self):
        r = upi_check.check("Rs 5000 credited to your a/c XX1234 on 12-10-26. -SBI")
        self.assertEqual((r["kind"], r["verdict"], r["direction"]), ("credited", "info", "in"))

    def test_sent_by_mistake(self):
        r = upi_check.check("Sir I sent you 5000 by mistake, please return the money to 9845012345@okaxis")
        self.assertEqual((r["kind"], r["verdict"]), ("mistake", "danger"))

    def test_brand_mismatch(self):
        r = upi_check.check("Flipkart: pay Rs 99 to 9123456789@ybl to confirm your order")
        keys = [f["key"] for f in r["flags"]]
        self.assertIn("brand_mismatch", keys)
        self.assertIn("personal_vpa", keys)

    def test_nothing_found(self):
        r = upi_check.check("see you tomorrow")
        self.assertEqual((r["kind"], r["verdict"], r["steps"]), ("none", "none", []))

    def test_email_is_not_a_upi_id(self):
        self.assertEqual(upi_check.check("mail me at ravi@gmail.com")["kind"], "none")

    def test_languages(self):
        for lang in ("hi", "bn"):
            r = upi_check.check("Ramesh has requested Rs 500. Approve to receive cashback", lang=lang)
            self.assertEqual(r["language"], lang)
            self.assertTrue(re.search(r"[ऀ-৿]", r["truth"]))
            self.assertTrue(all(re.search(r"[ऀ-৿]", f["title"]) for f in r["flags"]))

    @unittest.skipUnless(HAS_QR, "OpenCV with QR encoder not installed")
    def test_decodes_qr_image(self):
        uri = "upi://pay?pa=refund.desk@ybl&pn=Sunil%20Yadav&am=4999&cu=INR&tn=Flipkart%20refund"
        payloads = upi_check.decode_qr(qr_png(uri))
        self.assertEqual(payloads, [uri])
        r = upi_check.check("Scan this QR to receive your Flipkart refund", payloads)
        self.assertEqual((r["kind"], r["verdict"], r["amount"]), ("qr", "danger", "₹4,999"))
        self.assertEqual(r["payee"]["app"], "PhonePe")

    @unittest.skipUnless(HAS_QR, "OpenCV with QR encoder not installed")
    def test_link_qr_is_checked_as_a_link(self):
        r = upi_check.check("", upi_check.decode_qr(qr_png("http://sbi-kyc-update.xyz/login")))
        self.assertEqual(r["kind"], "link_qr")
        self.assertIn("risky_link", [f["key"] for f in r["flags"]])

    def test_bundled_sample_image(self):
        if not HAS_QR:
            self.skipTest("OpenCV not installed")
        path = os.path.join(os.path.dirname(__file__), "..", "static", "samples", "refund-qr.png")
        with open(path, "rb") as fh:
            self.assertTrue(upi_check.decode_qr(fh.read())[0].startswith("upi://pay?pa=refund.desk4471@ybl"))


class CallTacticsTest(unittest.TestCase):
    def test_digital_arrest_call(self):
        t = ("I am calling from CBI crime branch. Drugs found in your parcel. Do not tell anyone. "
             "Transfer your savings to the RBI verification account immediately.")
        ids = [h["id"] for h in call_tactics.scan(t)]
        for expected in ("authority", "secrecy", "safe_account", "urgency"):
            self.assertIn(expected, ids)
        self.assertEqual(call_tactics.risk(ids), "scam")

    def test_hindi_and_bengali(self):
        self.assertIn("authority", [h["id"] for h in call_tactics.scan("मैं पुलिस से बोल रहा हूँ, किसी को मत बताना")])
        self.assertIn("secrecy", [h["id"] for h in call_tactics.scan("এটা কাউকে বলবেন না")])

    def test_normal_call(self):
        self.assertEqual(call_tactics.scan("Hi Maa, I'll be home by eight. Keep dinner for me."), [])
        self.assertEqual(call_tactics.risk([]), "listening")

    def test_patterns_avoid_python_only_syntax(self):
        # The browser compiles these with new RegExp(p, 'iu'); keep them portable.
        for t in call_tactics.TACTICS:
            for p in t["patterns"]:
                self.assertNotRegex(p, r"\(\?[aiLmsux]|\(\?P<|\(\?<[=!]|\\A|\\Z", p)
            for lang in ("en", "hi", "bn"):
                self.assertTrue(t["title"][lang] and t["say"][lang])


class PaymentReceiptTest(unittest.TestCase):
    def test_bank_sms(self):
        out = payment_receipt.extract("Rs.25,000.00 debited from A/c XX4521 on 12-10-26 to VPA rbi.verify77@ybl "
                                      "(UPI Ref No 428615937204). -SBI")
        f = out["fields"]
        self.assertEqual((f["amount"], f["utr"], f["payee_vpa"], f["bank"], f["date"]),
                         ("25000.00", "428615937204", "rbi.verify77@ybl", "SBI", "12-10-26"))
        self.assertIsNone(f["payee_name"])

    def test_gpay_receipt(self):
        out = payment_receipt.extract("Google Pay\n₹4,999\nPaid to Ramesh Kumar\nramesh.k77@okaxis\n12 Oct 2026, 9:42 pm\n"
                                      "UPI transaction ID\n428611223344\nFrom: HDFC Bank 4521")
        f = out["fields"]
        self.assertEqual((f["amount"], f["payee_name"], f["utr"], f["app"], f["time"]),
                         ("4999", "Ramesh Kumar", "428611223344", "Google Pay", "9:42 pm"))

    def test_nothing_found(self):
        self.assertEqual(payment_receipt.extract("hello")["found"], [])


class ToolsApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_pages_render(self):
        for path in ("/chat-check", "/upi-check", "/call-copilot", "/paid", "/privacy", "/terms"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, path)
            self.assertNotIn("—", res.get_data(as_text=True), path)

    def test_chat_check_text(self):
        data = self.client.post("/api/chat-check", json={"text": TASK_CHAT}).get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["result"]["script"]["id"], "task_scam")

    def test_chat_check_whatsapp_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("_chat.txt", TASK_CHAT)
        buf.seek(0)
        data = self.client.post("/api/chat-check", data={"chat": (buf, "WhatsApp Chat.zip")},
                                content_type="multipart/form-data").get_json()
        self.assertEqual(data["result"]["script"]["id"], "task_scam")

    def test_chat_check_rejects_other_files(self):
        res = self.client.post("/api/chat-check", data={"chat": (io.BytesIO(b"x"), "chat.pdf")},
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.post("/api/chat-check", json={"text": " "}).status_code, 400)

    def test_upi_check_text(self):
        data = self.client.post("/api/upi-check", data={"text": "Ravi has requested Rs 300. Approve to receive cashback",
                                                        "language": "hi"}).get_json()
        self.assertEqual(data["result"]["verdict"], "danger")
        self.assertEqual(data["result"]["language"], "hi")

    @unittest.skipUnless(HAS_QR, "OpenCV with QR encoder not installed")
    def test_upi_check_qr_image(self):
        img = qr_png("upi://pay?pa=9876543210@ybl&pn=Ramesh&am=100")
        data = self.client.post("/api/upi-check", data={"image": (io.BytesIO(img), "qr.png", "image/png")},
                                content_type="multipart/form-data").get_json()
        self.assertEqual(data["result"]["kind"], "qr")
        self.assertEqual(data["result"]["amount"], "₹100")

    def test_upi_check_validation(self):
        self.assertEqual(self.client.post("/api/upi-check", data={"text": ""}).status_code, 400)
        res = self.client.post("/api/upi-check", data={"image": (io.BytesIO(b"not an image"), "x.png", "image/png")},
                               content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    def test_paid_extract(self):
        data = self.client.post("/api/paid/extract", data={"text": "Rs 999 debited, UPI Ref No 123456789012"}).get_json()
        self.assertEqual(data["fields"]["utr"], "123456789012")
        self.assertEqual(self.client.post("/api/paid/extract", data={"text": ""}).status_code, 400)

    def test_call_tactics_api_matches_page_data(self):
        api = self.client.get("/api/call-tactics").get_json()["tactics"]
        page = self.client.get("/call-copilot").get_data(as_text=True)
        embedded = json.loads(re.search(r'id="tactics-data">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(api, embedded)


if __name__ == "__main__":
    unittest.main()
