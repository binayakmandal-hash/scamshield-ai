"""PUBLIC_MODE isolation (deployed website) and upgrading old databases."""
import json
import os
import sqlite3
import tempfile
import unittest

os.environ["AI_PROVIDER"] = "none"
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))

import app as app_module  # noqa: E402
import database as db  # noqa: E402
from config import Config  # noqa: E402


class PublicModeIsolationTest(unittest.TestCase):
    def setUp(self):
        Config.PUBLIC_MODE = True
        self.alice = app_module.app.test_client()
        self.bob = app_module.app.test_client()

    def tearDown(self):
        Config.PUBLIC_MODE = False

    def test_visitors_do_not_share_history_learning_or_demo_inbox(self):
        self.alice.post("/api/mail/demo/scan", json={"reset": True})
        self.bob.post("/api/mail/demo/scan", json={"reset": True})

        # Alice opens an email (saved to her history) and marks one as spam
        a = self.alice.get("/api/mail/demo/demo-bank").get_json()
        self.alice.post("/api/mail/demo/demo-prize/action", json={"action": "block"})

        # Bob sees none of it
        self.assertEqual(self.bob.get("/api/history").get_json()["items"], [])
        self.assertEqual(self.bob.get(f"/api/history/{a['id']}").status_code, 404)
        self.assertEqual(self.bob.get(f"/analysis/{a['id']}").status_code, 404)
        self.assertEqual(self.bob.get("/api/learning").get_json()["senders"], [])
        self.assertEqual(self.bob.get("/api/learning").get_json()["feedback"]["scam"], 0)
        bob_ids = [i["id"] for i in self.bob.post("/api/mail/demo/scan", json={}).get_json()["items"]]
        self.assertIn("demo-prize", bob_ids)  # Alice's block didn't touch Bob's inbox

        # Alice still has her own data
        self.assertEqual(len(self.alice.get("/api/history").get_json()["items"]), 1)
        self.assertEqual(self.alice.get("/api/learning").get_json()["feedback"]["scam"], 1)

    def test_gmail_tokens_are_per_visitor(self):
        svc = app_module.mail
        with app_module.app.test_request_context():
            from flask import session
            session["uid"] = "a" * 32
            a = svc.gmail()
        with app_module.app.test_request_context():
            from flask import session
            session["uid"] = "b" * 32
            b = svc.gmail()
        self.assertNotEqual(a.token_file, b.token_file)
        self.assertTrue(a.token_file.endswith("a" * 32 + ".json"))


class MigrationTest(unittest.TestCase):
    def test_old_database_is_upgraded_without_losing_data(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE analyses (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT NOT NULL,
              preview TEXT NOT NULL, message TEXT NOT NULL, risk_score INTEGER NOT NULL, risk_level TEXT NOT NULL,
              categories TEXT NOT NULL, engine TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE training_examples (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              source TEXT NOT NULL, ref TEXT, label INTEGER NOT NULL, sender TEXT, text TEXT NOT NULL);
            CREATE TABLE sender_rules (sender TEXT PRIMARY KEY, kind TEXT NOT NULL, filter_id TEXT, created_at TEXT NOT NULL);
            CREATE TABLE learner_model (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        conn.execute("INSERT INTO analyses VALUES ('a1','2026-10-01','text','p','m',80,'Very High Risk','[]','rules',?)",
                     (json.dumps({"red_flags": []}),))
        conn.execute("INSERT INTO training_examples (created_at, source, ref, label, sender, text) "
                     "VALUES ('x','feedback','demo:1',1,'a@b.com','scam text')")
        conn.execute("INSERT INTO sender_rules VALUES ('bank@x.com','trusted',NULL,'x')")
        conn.commit()
        conn.close()

        db.init_db(path)
        self.assertEqual(len(db.list_analyses(path)), 1)
        self.assertEqual(db.example_counts(path)["feedback"]["scam"], 1)
        self.assertEqual(db.get_sender_rule(path, "bank@x.com")["kind"], "trusted")
        db.init_db(path)  # running again is safe


if __name__ == "__main__":
    unittest.main()
