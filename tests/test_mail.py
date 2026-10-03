"""Gmail, email scoring, learning and inbox routes. Google is mocked, so no account or network is needed."""
import base64
import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ["AI_PROVIDER"] = "none"
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))

import database as db  # noqa: E402
from services.demo_inbox import DemoMailbox  # noqa: E402
from services.email_pipeline import quick_analyze  # noqa: E402
from services.gmail_client import GmailClient, GmailError, parse_message  # noqa: E402
from services.learner import Learner  # noqa: E402


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def fake_resp(status=200, data=None):
    r = mock.Mock(status_code=status, content=b"x" if data is not None else b"")
    r.json.return_value = data or {}
    r.text = json.dumps(data or {})
    return r


class ParseMessageTest(unittest.TestCase):
    def test_html_email_exposes_hidden_link_and_auth(self):
        msg = {
            "id": "m1", "threadId": "t1", "snippet": "Verify now", "internalDate": "1700000000000", "labelIds": ["INBOX"],
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": '"SBI Alerts" <alerts@sbi-secure.xyz>'},
                    {"name": "Subject", "value": "Account blocked"},
                    {"name": "Authentication-Results", "value": "mx.google.com; spf=fail smtp.mailfrom=x; dkim=none; dmarc=fail"},
                ],
                "parts": [{"mimeType": "text/html", "body": {"data": b64(
                    '<p>Click <a href="http://sbi-kyc-verify.xyz/login">www.onlinesbi.sbi</a> to verify.</p>'
                    "<script>evil()</script>")}}],
            },
        }
        m = parse_message(msg)
        self.assertEqual(m["from_email"], "alerts@sbi-secure.xyz")
        self.assertEqual(m["from_name"], "SBI Alerts")
        self.assertIn("http://sbi-kyc-verify.xyz/login", m["links"])  # real target, not the anchor text
        self.assertNotIn("evil", m["body"])
        self.assertEqual(m["auth"], {"spf": "fail", "dkim": "none", "dmarc": "fail"})


class GmailClientTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cfg = SimpleNamespace(GMAIL_REDIRECT_URI="http://127.0.0.1:5000/oauth2callback",
                                   GMAIL_TOKEN_FILE=os.path.join(self.dir, "tok.json"),
                                   GOOGLE_CLIENT_ID="cid", GOOGLE_CLIENT_SECRET="sec",
                                   GOOGLE_CLIENT_SECRETS_FILE="")
        self.client = GmailClient(self.cfg)

    def test_auth_url_requests_needed_scopes(self):
        url = self.client.auth_url("st")
        self.assertIn("gmail.modify", url)
        self.assertIn("gmail.settings.basic", url)
        self.assertIn("access_type=offline", url)

    def test_reads_client_secret_file(self):
        path = os.path.join(self.dir, "client_secret.json")
        with open(path, "w") as fh:
            json.dump({"web": {"client_id": "abc", "client_secret": "xyz"}}, fh)
        cfg = SimpleNamespace(**{**vars(self.cfg), "GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "",
                                 "GOOGLE_CLIENT_SECRETS_FILE": path})
        self.assertTrue(GmailClient(cfg).configured)

    def test_exchange_then_refresh_expired_token(self):
        with mock.patch("services.gmail_client.requests.post",
                        return_value=fake_resp(200, {"access_token": "a1", "refresh_token": "r1", "expires_in": 1})):
            self.client.exchange_code("code")
        self.assertTrue(self.client.connected)
        with open(self.cfg.GMAIL_TOKEN_FILE) as fh:
            tok = json.load(fh)
        tok["expires_at"] = time.time() - 10
        with open(self.cfg.GMAIL_TOKEN_FILE, "w") as fh:
            json.dump(tok, fh)
        with mock.patch("services.gmail_client.requests.post",
                        return_value=fake_resp(200, {"access_token": "a2", "expires_in": 3600})) as post:
            self.assertEqual(self.client._token(), "a2")
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "refresh_token")
        with open(self.cfg.GMAIL_TOKEN_FILE) as fh:
            self.assertEqual(json.load(fh)["refresh_token"], "r1")  # refresh token kept

    def test_move_to_spam_and_block_fallback(self):
        with open(self.cfg.GMAIL_TOKEN_FILE, "w") as fh:
            json.dump({"access_token": "a", "refresh_token": "r", "expires_at": time.time() + 3600}, fh)
        calls = []

        def fake_request(method, url, **kw):
            calls.append((method, url, kw.get("json")))
            if url.endswith("/settings/filters") and kw["json"]["action"].get("addLabelIds") == ["TRASH"]:
                return fake_resp(400, {"error": {"message": "invalid label"}})
            if url.endswith("/labels") and method == "GET":
                return fake_resp(200, {"labels": []})
            if url.endswith("/labels"):
                return fake_resp(200, {"id": "Label_9"})
            return fake_resp(200, {"id": "f1"})

        with mock.patch("services.gmail_client.requests.request", side_effect=fake_request):
            self.client.move_to_spam("m1")
            fid = self.client.block_sender("bad@x.com")
        self.assertEqual(calls[0][2], {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]})
        self.assertEqual(fid, "f1")
        self.assertEqual(calls[-1][2]["action"]["removeLabelIds"], ["INBOX", "UNREAD"])

    def test_not_connected_error(self):
        with self.assertRaises(GmailError):
            self.client.profile()


class EmailScoringTest(unittest.TestCase):
    def setUp(self):
        self.learner = Learner(os.environ["DATABASE_PATH"])
        self.box = DemoMailbox()

    def test_official_verified_sender_scores_low(self):
        r = quick_analyze(self.box.get_message("demo-hdfc-otp"), self.learner, None)
        self.assertEqual(r["risk_level"], "Low Risk")
        self.assertTrue(any("Verified sender" in t["title"] for t in r.get("trust_signals", [])))

    def test_free_provider_never_counts_as_verified(self):
        r = quick_analyze(self.box.get_message("demo-electricity"), self.learner, None)
        self.assertFalse(r.get("trust_signals"))

    def test_failed_dmarc_adds_points(self):
        r = quick_analyze(self.box.get_message("demo-netflix"), self.learner, None)
        self.assertIn("Sender verification failed", [b["signal"] for b in r["score_breakdown"]])

    def test_score_is_sum_of_breakdown(self):
        for mid in ("demo-bank", "demo-amazon", "demo-electricity"):
            r = quick_analyze(self.box.get_message(mid), self.learner, None)
            total = max(0, min(100, sum(b["points"] for b in r["score_breakdown"])))
            self.assertEqual(r["risk_score"], total, mid)

    def test_trusted_sender_lowers_score(self):
        mail = self.box.get_message("demo-electricity")
        before = quick_analyze(mail, self.learner, None)["risk_score"]
        after = quick_analyze(mail, self.learner, {"kind": "trusted"})["risk_score"]
        self.assertLess(after, before)


class InboxRoutesTest(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.c = app_module.app.test_client()
        self.c.post("/api/mail/demo/scan", json={"reset": True})

    def test_feedback_trains_and_undo_forgets(self):
        before = self.c.get("/api/learning").get_json()["feedback"]["scam"]
        r = self.c.post("/api/mail/demo/demo-job/action", json={"action": "spam"}).get_json()
        self.assertEqual(r["learning"]["feedback"]["scam"], before + 1)
        ids = [i["id"] for i in self.c.post("/api/mail/demo/scan", json={}).get_json()["items"]]
        self.assertNotIn("demo-job", ids)
        r = self.c.post("/api/mail/demo/demo-job/action", json={"action": "spam", "undo": True}).get_json()
        self.assertEqual(r["learning"]["feedback"]["scam"], before)

    def test_block_hides_sender_and_unblock_restores(self):
        self.c.post("/api/mail/demo/demo-prize/action", json={"action": "block"})
        rules = self.c.get("/api/learning").get_json()["senders"]
        self.assertTrue(any(r["kind"] == "blocked" for r in rules))
        self.c.post("/api/mail/demo/demo-prize/action", json={"action": "block", "undo": True})
        ids = [i["id"] for i in self.c.post("/api/mail/demo/scan", json={}).get_json()["items"]]
        self.assertIn("demo-prize", ids)

    def test_detail_returns_full_analysis(self):
        d = self.c.get("/api/mail/demo/demo-bank").get_json()
        self.assertTrue(d["ok"])
        self.assertIn("score_breakdown", d["result"])

    def test_gmail_requires_connection(self):
        self.assertEqual(self.c.post("/api/mail/gmail/scan", json={}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
