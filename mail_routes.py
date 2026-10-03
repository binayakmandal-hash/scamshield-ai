"""Inbox features: connect Gmail, scan, act on emails, learn from feedback.

Two mailboxes share the same routes:
  /api/mail/gmail/...  your real Gmail (after you connect it)
  /api/mail/demo/...   the built-in demo inbox (works offline, great for demos)
"""
import logging
import secrets
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, redirect, request, session, url_for

import database as db
from services.demo_inbox import DemoMailbox
from services.email_pipeline import deep_analyze, email_text, quick_analyze, summary_row
from services.gmail_client import GmailClient, GmailError
from services.learner import Learner

log = logging.getLogger(__name__)
bp = Blueprint("mail", __name__)

ACTIONS = {"spam", "trash", "block", "safe"}
LABELS = {"spam": 1, "trash": 1, "block": 1, "safe": 0}


class MailService:
    def __init__(self, config, analyzer):
        self.config = config
        self.db_path = config.DATABASE_PATH
        self.analyzer = analyzer
        self.gmail = GmailClient(config)
        self.demo = DemoMailbox()
        self.learner = Learner(self.db_path)
        self.mails = {}        # (mode, id) -> parsed email (kept in memory only)
        self.deep_cache = {}   # (mode, id, lang) -> full analysis

    def box(self, mode):
        if mode == "demo":
            return self.demo
        if mode == "gmail":
            if not self.gmail.connected:
                raise GmailError("Gmail isn't connected yet. Click 'Connect Gmail' first.")
            return self.gmail
        raise GmailError("Unknown mailbox.")

    def mail(self, mode, mid):
        key = (mode, mid)
        if key not in self.mails:
            self.mails[key] = self.box(mode).get_message(mid)
        return self.mails[key]

    def rule(self, mail):
        return db.get_sender_rule(self.db_path, mail.get("from_email"))


svc: MailService = None


def init_app(app, config, analyzer):
    global svc
    svc = MailService(config, analyzer)
    app.register_blueprint(bp)
    return svc


def _err(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def _lang(value):
    return value if value in ("en", "hi", "bn") else "en"


# --------------------------------------------------------------------------- #
# Gmail connection
# --------------------------------------------------------------------------- #
@bp.get("/gmail/connect")
def gmail_connect():
    if not svc.gmail.configured:
        return redirect(url_for("index") + "?gmail=not_configured#inbox")
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    return redirect(svc.gmail.auth_url(state))


@bp.get("/oauth2callback")
def gmail_callback():
    if request.args.get("error"):
        log.warning("Google sign-in returned an error: %s", request.args.get("error"))
        return redirect(url_for("index") + "?gmail=denied#inbox")
    if not request.args.get("state") or request.args.get("state") != session.pop("oauth_state", None):
        log.warning("Sign-in state didn't match. Open the app at http://127.0.0.1:5000 (not localhost) and try again.")
        return redirect(url_for("index") + "?gmail=bad_state#inbox")
    try:
        svc.gmail.exchange_code(request.args.get("code", ""))
    except GmailError as exc:
        log.warning("OAuth failed: %s", exc)
        return redirect(url_for("index") + "?gmail=failed#inbox")
    return redirect(url_for("index") + "?gmail=connected#inbox")


@bp.get("/api/gmail/status")
def gmail_status():
    info = {"ok": True, "configured": svc.gmail.configured, "connected": svc.gmail.connected, "email": None}
    if svc.gmail.connected:
        try:
            info["email"] = svc.gmail.profile().get("emailAddress")
        except GmailError as exc:
            info.update(connected=svc.gmail.connected, error=str(exc))
    return jsonify(info)


@bp.post("/api/gmail/disconnect")
def gmail_disconnect():
    svc.gmail.disconnect()
    svc.mails = {k: v for k, v in svc.mails.items() if k[0] != "gmail"}
    svc.deep_cache = {k: v for k, v in svc.deep_cache.items() if k[0] != "gmail"}
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Scanning and analysis
# --------------------------------------------------------------------------- #
@bp.post("/api/mail/<mode>/scan")
def scan(mode):
    payload = request.get_json(silent=True) or {}
    limit = max(1, min(int(payload.get("limit") or svc.config.GMAIL_SCAN_LIMIT), 50))
    try:
        box = svc.box(mode)
        if mode == "demo" and payload.get("reset"):
            box.reset()
        ids = box.list_messages(limit=limit, query=payload.get("query") or "in:inbox")
        with ThreadPoolExecutor(max_workers=8) as pool:
            mails = list(pool.map(lambda i: svc.mail(mode, i), ids))
    except GmailError as exc:
        return _err(str(exc), 409 if "connect" in str(exc).lower() else 502)

    rows = []
    for mail in mails:
        rule = svc.rule(mail)
        rows.append(summary_row(mail, quick_analyze(mail, svc.learner, rule), rule))
    rows.sort(key=lambda r: -(r.get("timestamp") or 0))
    high = sum(1 for r in rows if r["risk_level"] in ("High Risk", "Very High Risk"))
    return jsonify({"ok": True, "mode": mode, "items": rows, "high_risk": high, "learning": svc.learner.status()})


@bp.get("/api/mail/<mode>/<mid>")
def mail_detail(mode, mid):
    lang = _lang(request.args.get("lang"))
    try:
        mail = svc.mail(mode, mid)
    except (GmailError, KeyError) as exc:
        return _err(str(exc) or "Email not found", 404)
    rule = svc.rule(mail)
    key = (mode, mid, lang)
    if key not in svc.deep_cache:
        result = deep_analyze(mail, svc.analyzer, svc.learner, rule, lang)
        analysis_id = None
        if svc.config.SAVE_HISTORY:
            analysis_id = db.save_analysis(svc.db_path, email_text(mail), result, "gmail" if mode == "gmail" else "demo",
                                           redact=svc.config.REDACT_STORED_MESSAGES)
        svc.deep_cache[key] = (result, analysis_id)
    result, analysis_id = svc.deep_cache[key]
    return jsonify({"ok": True, "id": analysis_id, "source": "email", "language": lang, "message": email_text(mail),
                    "mail": summary_row(mail, result, rule), "result": result})


# --------------------------------------------------------------------------- #
# Actions (all reversible) + learning from them
# --------------------------------------------------------------------------- #
def _apply(mode, mid, action):
    box, mail = svc.box(mode), svc.mail(mode, mid)
    sender = mail.get("from_email", "")
    ref = f"{mode}:{mid}"
    if action == "spam":
        box.move_to_spam(mid)
    elif action == "trash":
        box.trash(mid)
    elif action == "block":
        filter_id = box.block_sender(sender)
        db.set_sender_rule(svc.db_path, sender, "blocked", filter_id)
        box.move_to_spam(mid)
    elif action == "safe":
        db.set_sender_rule(svc.db_path, sender, "trusted")
    db.add_example(svc.db_path, "feedback", LABELS[action], email_text(mail), sender, ref)
    _forget(mode, mid)


def _undo(mode, mid, action):
    box, mail = svc.box(mode), svc.mail(mode, mid)
    sender = mail.get("from_email", "")
    if action == "spam":
        box.restore_to_inbox(mid)
    elif action == "trash":
        box.untrash(mid)
    elif action == "block":
        rule = db.get_sender_rule(svc.db_path, sender)
        if rule and rule.get("filter_id"):
            box.unblock_sender(rule["filter_id"])
        db.delete_sender_rule(svc.db_path, sender)
        box.restore_to_inbox(mid)
    elif action == "safe":
        db.delete_sender_rule(svc.db_path, sender)
    db.remove_example(svc.db_path, "feedback", f"{mode}:{mid}")
    _forget(mode, mid)


def _forget(mode, mid):
    for key in [k for k in svc.deep_cache if k[0] == mode and k[1] == mid]:
        svc.deep_cache.pop(key, None)


@bp.post("/api/mail/<mode>/<mid>/action")
def mail_action(mode, mid):
    payload = request.get_json(silent=True) or {}
    action, undo = payload.get("action"), bool(payload.get("undo"))
    if action not in ACTIONS:
        return _err("Unknown action.")
    try:
        (_undo if undo else _apply)(mode, mid, action)
    except (GmailError, KeyError) as exc:
        return _err(str(exc) or "Email not found", 502)
    stats = svc.learner.retrain()
    return jsonify({"ok": True, "action": action, "undone": undo, "learning": {"ready": svc.learner.ready, **stats}})


@bp.post("/api/mail/<mode>/bulk")
def mail_bulk(mode):
    payload = request.get_json(silent=True) or {}
    action, ids = payload.get("action"), payload.get("ids") or []
    if action not in ("spam", "trash") or not isinstance(ids, list):
        return _err("Bulk actions support 'spam' or 'trash' with a list of ids.")
    done, failed = [], []
    for mid in ids[:50]:
        try:
            _apply(mode, str(mid), action)
            done.append(mid)
        except (GmailError, KeyError) as exc:
            failed.append({"id": mid, "error": str(exc)})
    stats = svc.learner.retrain()
    return jsonify({"ok": True, "done": done, "failed": failed, "learning": {"ready": svc.learner.ready, **stats}})


# --------------------------------------------------------------------------- #
# Learning
# --------------------------------------------------------------------------- #
@bp.get("/api/learning")
def learning_status():
    return jsonify({"ok": True, **svc.learner.status(), "senders": db.list_sender_rules(svc.db_path)})


@bp.post("/api/learning/retrain")
def learning_retrain():
    return jsonify({"ok": True, "ready": svc.learner.ready, **svc.learner.retrain()})


@bp.delete("/api/learning/feedback")
def learning_reset():
    db.clear_examples(svc.db_path, "feedback")
    return jsonify({"ok": True, "ready": svc.learner.ready, **svc.learner.retrain()})


@bp.delete("/api/learning/sender/<path:sender>")
def learning_forget_sender(sender):
    rule = db.get_sender_rule(svc.db_path, sender)
    if not rule:
        return _err("Sender not found", 404)
    if rule.get("filter_id"):
        try:
            box = svc.demo if rule["filter_id"].startswith("demo-") else svc.box("gmail")
            box.unblock_sender(rule["filter_id"])
        except GmailError as exc:
            return _err(f"Couldn't remove the Gmail filter: {exc}", 502)
    db.delete_sender_rule(svc.db_path, sender)
    return jsonify({"ok": True})
