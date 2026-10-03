"""End-to-end API tests. They run with AI turned off, so no model or network is needed."""
import os
import tempfile
import unittest
from unittest import mock

os.environ["AI_PROVIDER"] = "none"
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as app_module  # noqa: E402
from services.ai_analyzer import OllamaClient  # noqa: E402


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_analyze_saves_redacted_history(self):
        res = self.client.post("/api/analyze", json={"text": "Share the OTP 483920 now or your account will be blocked."})
        data = res.get_json()
        self.assertTrue(data["ok"])
        saved = self.client.get(f"/api/history/{data['id']}").get_json()["item"]
        self.assertNotIn("483920", saved["message"])

    def test_empty_text_rejected(self):
        self.assertEqual(self.client.post("/api/analyze", json={"text": "  "}).status_code, 400)

    def test_followups_work_without_ai(self):
        r = self.client.post("/api/analyze", json={"text": "You have won a lottery! Pay a processing fee today."}).get_json()
        ctx = {"message": r["message"], "analysis": r["result"], "language": "hi"}
        self.assertEqual(len(self.client.post("/api/action-plan", json=ctx).get_json()["steps"]), 3)
        self.assertTrue(self.client.post("/api/eli12", json=ctx).get_json()["explanation"])
        self.assertTrue(self.client.post("/api/family-note", json=ctx).get_json()["note"])
        self.assertTrue(self.client.post("/api/chat", json={**ctx, "question": "How do I verify?"}).get_json()["answer"])

    def test_pages_render(self):
        for path in ("/", "/history", "/dashboard"):
            self.assertEqual(self.client.get(path).status_code, 200, path)


class OllamaClientTest(unittest.TestCase):
    """Checks the request we send to Ollama, using a fake HTTP layer."""

    def test_sends_json_format_and_parses_reply(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = {"message": {"content": '{"answer": "hi"}'}}
        with mock.patch("services.ai_analyzer.requests.post", return_value=fake) as post:
            out = OllamaClient("http://localhost:11434", "gemma4:e4b").generate_json("q", system="s", image=b"img",
                                                                                   mime="image/png")
        self.assertEqual(out, {"answer": "hi"})
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gemma4:e4b")
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["messages"][0], {"role": "system", "content": "s"})
        self.assertIn("images", body["messages"][1])


if __name__ == "__main__":
    unittest.main()
