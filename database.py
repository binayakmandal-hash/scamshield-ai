"""SQLite storage: analysis history, learning data, sender rules.

Every row belongs to a user id ("uid"):
  * running locally, everything uses uid "local" (single user, nothing changes);
  * in PUBLIC_MODE (e.g. on Render), each browser session gets its own uid,
    so visitors never see each other's history, senders or feedback.

Privacy-first: sensitive-looking values are masked before they are written,
and screenshots are never stored.
"""
import json
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone

LOCAL = "local"

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    uid         TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,          -- 'gmail', 'demo', 'screenshot' or 'text'
    preview     TEXT NOT NULL,          -- first ~140 chars (redacted)
    message     TEXT NOT NULL,          -- redacted message text
    risk_score  INTEGER NOT NULL,
    risk_level  TEXT NOT NULL,
    categories  TEXT NOT NULL,          -- JSON list
    engine      TEXT NOT NULL,          -- 'ai' (open-weight model) or 'rules'
    result      TEXT NOT NULL           -- JSON analysis (redacted)
);

-- Labelled examples the learner trains on.
--   source: 'feedback' (a user's clicks, private to that uid), 'dataset' (shared, imported with train.py)
--   label:  1 = scam / phishing, 0 = safe
CREATE TABLE IF NOT EXISTS training_examples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    uid         TEXT,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,
    ref         TEXT,                   -- e.g. Gmail message id, so a re-label replaces the old one
    label       INTEGER NOT NULL,
    sender      TEXT,
    text        TEXT NOT NULL           -- redacted
);

-- Senders a user trusted or blocked.
CREATE TABLE IF NOT EXISTS sender_rules (
    uid         TEXT NOT NULL DEFAULT 'local',
    sender      TEXT NOT NULL,          -- lower-case email address
    kind        TEXT NOT NULL,          -- 'trusted' or 'blocked'
    filter_id   TEXT,                   -- Gmail filter id for blocked senders
    created_at  TEXT NOT NULL,
    PRIMARY KEY (uid, sender)
);

-- Trained models, one per user.
CREATE TABLE IF NOT EXISTS learner_models (
    uid         TEXT PRIMARY KEY,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_analyses_uid ON analyses(uid, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_train_ref ON training_examples(uid, source, ref);
"""

HIGH_RISK_LEVELS = {"High Risk", "Very High Risk"}

_DIGITS = re.compile(r"\d{6,}")
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


# --------------------------------------------------------------------------- #
# Redaction
# --------------------------------------------------------------------------- #
def redact_text(text: str) -> str:
    """Mask long numbers (OTPs, phone/account/Aadhaar numbers) and email usernames.

    Keeps the last two digits so a user can still recognise the message.
    """
    if not text:
        return text
    text = _DIGITS.sub(lambda m: "•" * (len(m.group()) - 2) + m.group()[-2:], text)
    text = _EMAIL.sub(lambda m: f"{m.group(1)}•••@{m.group(2)}", text)
    return text


def redact_deep(value):
    """Apply redact_text to every string inside a JSON-like structure.

    Using the same function on the message *and* the analysis keeps evidence
    phrases matchable, so highlights still work when an analysis is reopened.
    """
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_deep(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_deep(v) for k, v in value.items()}
    return value


# --------------------------------------------------------------------------- #
# Connection + migrations
# --------------------------------------------------------------------------- #
@contextmanager
def _connect(db_path: str):
    """Open a connection, commit on success, and always close it."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        # Upgrade databases created by older versions (before per-user rows).
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "analyses" in tables and "uid" not in _columns(conn, "analyses"):
            conn.execute("ALTER TABLE analyses ADD COLUMN uid TEXT NOT NULL DEFAULT 'local'")
        if "training_examples" in tables and "uid" not in _columns(conn, "training_examples"):
            conn.execute("ALTER TABLE training_examples ADD COLUMN uid TEXT")
            conn.execute("UPDATE training_examples SET uid = 'local' WHERE source = 'feedback'")
        if "sender_rules" in tables and "uid" not in _columns(conn, "sender_rules"):
            conn.execute("ALTER TABLE sender_rules RENAME TO sender_rules_old")
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO sender_rules (uid, sender, kind, filter_id, created_at) "
                         "SELECT 'local', sender, kind, filter_id, created_at FROM sender_rules_old")
            conn.execute("DROP TABLE sender_rules_old")
        conn.executescript(SCHEMA)
        conn.executescript(INDEXES)
        conn.execute("DROP TABLE IF EXISTS learner_model")  # replaced by learner_models


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Analyses (history)
# --------------------------------------------------------------------------- #
def save_analysis(db_path, message, result, source="text", redact=True, uid=LOCAL) -> str:
    analysis_id = uuid.uuid4().hex[:12]
    stored_message = redact_text(message) if redact else message
    stored_result = redact_deep(result) if redact else result
    preview = re.sub(r"\s+", " ", stored_message).strip()[:140]
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO analyses (id, uid, created_at, source, preview, message, risk_score,"
            " risk_level, categories, engine, result) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (analysis_id, uid, _now(), source, preview, stored_message, int(result.get("risk_score", 0)),
             result.get("risk_level", "Low Risk"), json.dumps(result.get("categories", [])),
             result.get("engine", "rules"), json.dumps(stored_result, ensure_ascii=False)),
        )
    return analysis_id


def _row_summary(row) -> dict:
    return {
        "id": row["id"], "created_at": row["created_at"], "source": row["source"], "preview": row["preview"],
        "risk_score": row["risk_score"], "risk_level": row["risk_level"],
        "categories": json.loads(row["categories"]), "engine": row["engine"],
    }


def list_analyses(db_path, limit=100, uid=LOCAL) -> list:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM analyses WHERE uid = ? ORDER BY created_at DESC LIMIT ?",
                            (uid, limit)).fetchall()
    return [_row_summary(r) for r in rows]


def get_analysis(db_path, analysis_id, uid=LOCAL):
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ? AND uid = ?", (analysis_id, uid)).fetchone()
    if not row:
        return None
    data = _row_summary(row)
    data["message"] = row["message"]
    data["result"] = json.loads(row["result"])
    return data


def delete_analysis(db_path, analysis_id, uid=LOCAL) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM analyses WHERE id = ? AND uid = ?", (analysis_id, uid))
    return cur.rowcount > 0


def clear_history(db_path, uid=LOCAL) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM analyses WHERE uid = ?", (uid,))
    return cur.rowcount


def get_stats(db_path, uid=LOCAL) -> dict:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT risk_level, categories, result FROM analyses WHERE uid = ?", (uid,)).fetchall()

    levels, categories, warning_signs = Counter(), Counter(), set()
    for r in rows:
        levels[r["risk_level"]] += 1
        for c in json.loads(r["categories"]):
            categories[c] += 1
        try:
            for flag in json.loads(r["result"]).get("red_flags", []):
                warning_signs.add(flag.get("title", "").strip().lower())
        except (ValueError, AttributeError):
            pass
    warning_signs.discard("")
    return {
        "total": len(rows),
        "high_risk": sum(v for k, v in levels.items() if k in HIGH_RISK_LEVELS),
        "most_common_category": categories.most_common(1)[0][0] if categories else None,
        "tips_learned": len(warning_signs),  # distinct warning signs explained to this user
        "levels": {lvl: levels.get(lvl, 0) for lvl in ("Low Risk", "Suspicious", "High Risk", "Very High Risk")},
        "categories": categories.most_common(8),
    }


# --------------------------------------------------------------------------- #
# Learning data
# --------------------------------------------------------------------------- #
def add_example(db_path, source, label, text, sender=None, ref=None, redact=True, uid=LOCAL):
    """Store a labelled example. With a ref, re-labelling replaces the earlier label."""
    text = redact_text(text) if redact else text
    with _connect(db_path) as conn:
        if ref:
            conn.execute("DELETE FROM training_examples WHERE uid IS ? AND source = ? AND ref = ?", (uid, source, ref))
        conn.execute(
            "INSERT INTO training_examples (uid, created_at, source, ref, label, sender, text) VALUES (?,?,?,?,?,?,?)",
            (uid, _now(), source, ref, int(label), (sender or "").lower() or None, text[:8000]),
        )


def add_examples_bulk(db_path, rows, source="dataset"):
    """Shared examples (uid NULL) from a dataset. rows: iterable of (label, text)."""
    stamp = _now()
    data = [(None, stamp, source, None, int(label), None, redact_text(text)[:8000]) for label, text in rows if text]
    with _connect(db_path) as conn:
        conn.executemany("INSERT INTO training_examples (uid, created_at, source, ref, label, sender, text) "
                         "VALUES (?,?,?,?,?,?,?)", data)
    return len(data)


def remove_example(db_path, source, ref, uid=LOCAL):
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM training_examples WHERE uid IS ? AND source = ? AND ref = ?", (uid, source, ref))


def list_examples(db_path, uid=LOCAL):
    """Shared dataset rows plus this user's own feedback."""
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT source, label, sender, text FROM training_examples "
                            "WHERE uid IS NULL OR uid = ?", (uid,)).fetchall()
    return [dict(r) for r in rows]


def example_counts(db_path, uid=LOCAL):
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT source, label, COUNT(*) AS n FROM training_examples "
                            "WHERE uid IS NULL OR uid = ? GROUP BY source, label", (uid,)).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["source"], {"scam": 0, "safe": 0})["scam" if r["label"] else "safe"] = r["n"]
    return out


def clear_examples(db_path, source=None, uid=None):
    """Delete examples. With uid, only that user's; 'dataset' rows are shared (uid NULL)."""
    query, args = "DELETE FROM training_examples WHERE 1=1", []
    if source:
        query += " AND source = ?"
        args.append(source)
    if uid is not None:
        query += " AND uid = ?"
        args.append(uid)
    with _connect(db_path) as conn:
        conn.execute(query, args)


# --------------------------------------------------------------------------- #
# Sender rules
# --------------------------------------------------------------------------- #
def set_sender_rule(db_path, sender, kind, filter_id=None, uid=LOCAL):
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO sender_rules (uid, sender, kind, filter_id, created_at) VALUES (?,?,?,?,?)",
                     (uid, sender.lower(), kind, filter_id, _now()))


def get_sender_rule(db_path, sender, uid=LOCAL):
    if not sender:
        return None
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM sender_rules WHERE uid = ? AND sender = ?", (uid, sender.lower())).fetchone()
    return dict(row) if row else None


def delete_sender_rule(db_path, sender, uid=LOCAL):
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM sender_rules WHERE uid = ? AND sender = ?", (uid, sender.lower()))


def list_sender_rules(db_path, uid=LOCAL):
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT sender, kind, filter_id, created_at FROM sender_rules WHERE uid = ? "
                            "ORDER BY created_at DESC", (uid,)).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
def save_model(db_path, data: dict, uid=LOCAL):
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO learner_models (uid, data, updated_at) VALUES (?, ?, ?)",
                     (uid, json.dumps(data), _now()))


def load_model(db_path, uid=LOCAL):
    with _connect(db_path) as conn:
        row = conn.execute("SELECT data FROM learner_models WHERE uid = ?", (uid,)).fetchone()
    return json.loads(row["data"]) if row else None


def clear_models(db_path):
    """Forget all saved models (e.g. after importing a dataset) so they retrain."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM learner_models")
