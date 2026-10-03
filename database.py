"""SQLite storage for analysis history.

Privacy-first: only what is needed to re-open an analysis is stored, and
(by default) sensitive-looking values are masked before they are written.
Screenshots are never stored on the server.
"""
import json
import re
import sqlite3
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,          -- 'text' or 'screenshot'
    preview     TEXT NOT NULL,          -- first ~140 chars (redacted)
    message     TEXT NOT NULL,          -- redacted message text
    risk_score  INTEGER NOT NULL,
    risk_level  TEXT NOT NULL,
    categories  TEXT NOT NULL,          -- JSON list
    engine      TEXT NOT NULL,          -- 'ai' (open-weight model) or 'rules'
    result      TEXT NOT NULL           -- JSON analysis (redacted)
);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);

-- Labelled examples the learner trains on.
--   source: 'feedback' (your clicks), 'dataset' (imported with train.py)
--   label:  1 = scam / phishing, 0 = safe
CREATE TABLE IF NOT EXISTS training_examples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,
    ref         TEXT,                   -- e.g. Gmail message id, so a re-label replaces the old one
    label       INTEGER NOT NULL,
    sender      TEXT,
    text        TEXT NOT NULL           -- redacted
);
CREATE INDEX IF NOT EXISTS idx_train_ref ON training_examples(source, ref);

-- Senders you trusted or blocked.
CREATE TABLE IF NOT EXISTS sender_rules (
    sender      TEXT PRIMARY KEY,       -- lower-case email address
    kind        TEXT NOT NULL,          -- 'trusted' or 'blocked'
    filter_id   TEXT,                   -- Gmail filter id for blocked senders
    created_at  TEXT NOT NULL
);

-- The trained model (one row).
CREATE TABLE IF NOT EXISTS learner_model (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
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
# Connection helpers
# --------------------------------------------------------------------------- #
@contextmanager
def _connect(db_path: str):
    """Open a connection, commit on success, and always close it."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_analysis(db_path, message, result, source="text", redact=True) -> str:
    analysis_id = uuid.uuid4().hex[:12]
    stored_message = redact_text(message) if redact else message
    stored_result = redact_deep(result) if redact else result
    preview = re.sub(r"\s+", " ", stored_message).strip()[:140]
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO analyses (id, created_at, source, preview, message, risk_score,"
            " risk_level, categories, engine, result) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                analysis_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source,
                preview,
                stored_message,
                int(result.get("risk_score", 0)),
                result.get("risk_level", "Low Risk"),
                json.dumps(result.get("categories", [])),
                result.get("engine", "rules"),
                json.dumps(stored_result, ensure_ascii=False),
            ),
        )
    return analysis_id


def _row_summary(row) -> dict:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "source": row["source"],
        "preview": row["preview"],
        "risk_score": row["risk_score"],
        "risk_level": row["risk_level"],
        "categories": json.loads(row["categories"]),
        "engine": row["engine"],
    }


def list_analyses(db_path, limit=100) -> list:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_summary(r) for r in rows]


def get_analysis(db_path, analysis_id):
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return None
    data = _row_summary(row)
    data["message"] = row["message"]
    data["result"] = json.loads(row["result"])
    return data


def delete_analysis(db_path, analysis_id) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    return cur.rowcount > 0


def clear_history(db_path) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM analyses")
    return cur.rowcount


def get_stats(db_path) -> dict:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT risk_level, categories, result FROM analyses").fetchall()

    levels = Counter()
    categories = Counter()
    warning_signs = set()
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
        # "Safety tips learned" = distinct warning signs the user has seen explained.
        "tips_learned": len(warning_signs),
        "levels": {
            lvl: levels.get(lvl, 0)
            for lvl in ("Low Risk", "Suspicious", "High Risk", "Very High Risk")
        },
        "categories": categories.most_common(8),
    }


# --------------------------------------------------------------------------- #
# Learning data
# --------------------------------------------------------------------------- #
def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_example(db_path, source, label, text, sender=None, ref=None, redact=True):
    """Store a labelled example. With a ref, re-labelling replaces the earlier label."""
    text = redact_text(text) if redact else text
    with _connect(db_path) as conn:
        if ref:
            conn.execute("DELETE FROM training_examples WHERE source = ? AND ref = ?", (source, ref))
        conn.execute(
            "INSERT INTO training_examples (created_at, source, ref, label, sender, text) VALUES (?,?,?,?,?,?)",
            (_now(), source, ref, int(label), (sender or "").lower() or None, text[:8000]),
        )


def add_examples_bulk(db_path, rows, source="dataset"):
    """rows: iterable of (label, text). Returns how many were added."""
    stamp = _now()
    data = [(stamp, source, None, int(label), None, redact_text(text)[:8000]) for label, text in rows if text]
    with _connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO training_examples (created_at, source, ref, label, sender, text) VALUES (?,?,?,?,?,?)", data)
    return len(data)


def remove_example(db_path, source, ref):
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM training_examples WHERE source = ? AND ref = ?", (source, ref))


def list_examples(db_path):
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT source, label, sender, text FROM training_examples").fetchall()
    return [dict(r) for r in rows]


def example_counts(db_path):
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT source, label, COUNT(*) AS n FROM training_examples GROUP BY source, label").fetchall()
    out = {}
    for r in rows:
        out.setdefault(r["source"], {"scam": 0, "safe": 0})["scam" if r["label"] else "safe"] = r["n"]
    return out


def clear_examples(db_path, source=None):
    with _connect(db_path) as conn:
        if source:
            conn.execute("DELETE FROM training_examples WHERE source = ?", (source,))
        else:
            conn.execute("DELETE FROM training_examples")


def set_sender_rule(db_path, sender, kind, filter_id=None):
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO sender_rules (sender, kind, filter_id, created_at) VALUES (?,?,?,?)",
                     (sender.lower(), kind, filter_id, _now()))


def get_sender_rule(db_path, sender):
    if not sender:
        return None
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM sender_rules WHERE sender = ?", (sender.lower(),)).fetchone()
    return dict(row) if row else None


def delete_sender_rule(db_path, sender):
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM sender_rules WHERE sender = ?", (sender.lower(),))


def list_sender_rules(db_path):
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM sender_rules ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def save_model(db_path, data: dict):
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO learner_model (id, data, updated_at) VALUES (1, ?, ?)",
                     (json.dumps(data), _now()))


def load_model(db_path):
    with _connect(db_path) as conn:
        row = conn.execute("SELECT data FROM learner_model WHERE id = 1").fetchone()
    return json.loads(row["data"]) if row else None
