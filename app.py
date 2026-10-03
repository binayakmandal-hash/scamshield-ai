"""ScamShield AI - Flask entry point.

Run:  python app.py      then open http://127.0.0.1:5000
"""
import io
import time
import logging

from flask import Flask, abort, jsonify, render_template, request
from PIL import Image, UnidentifiedImageError

import database as db
from config import Config
import mail_routes
from users import current_uid
from services.ai_analyzer import AIUnavailable, ScamAnalyzer, build_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.config.from_object(Config)

analyzer = ScamAnalyzer(build_client(Config))
db.init_db(Config.DATABASE_PATH)
mail = mail_routes.init_app(app, Config, analyzer)  # Gmail inbox, demo inbox and learning

VALID_LANGS = {"en", "hi", "bn"}


def _lang(value) -> str:
    return value if value in VALID_LANGS else "en"


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


# --------------------------------------------------------------------------- #
# Public deployments: per-visitor limit on requests that call the AI model
# --------------------------------------------------------------------------- #
_AI_ENDPOINTS = ("/api/analyze", "/api/chat", "/api/eli12", "/api/action-plan", "/api/family-note")
_ai_calls = {}


@app.before_request
def limit_ai_usage():
    if not Config.PUBLIC_MODE:
        return None
    path = request.path
    is_ai = path in _AI_ENDPOINTS or (request.method == "GET" and path.startswith("/api/mail/") and path.count("/") == 4)
    if not is_ai:
        return None
    now = time.time()
    calls = [t for t in _ai_calls.get(current_uid(), []) if now - t < 3600]
    if len(calls) >= Config.AI_REQUESTS_PER_HOUR:
        return _error("You've reached the hourly limit for AI analyses on this demo site. Try again later, "
                      "or run ScamShield on your own computer for unlimited use.", 429)
    calls.append(now)
    _ai_calls[current_uid()] = calls
    return None


@app.context_processor
def inject_globals():
    ready, reason = analyzer.llm.is_ready() if analyzer.llm.enabled else (False, "AI is turned off (AI_PROVIDER=none)")
    return {"ai_enabled": ready, "ai_model": analyzer.llm.label, "ai_reason": reason,
            "gmail_configured": mail.gmail().configured, "gmail_connected": mail.gmail().connected,
            "public_mode": Config.PUBLIC_MODE}


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return render_template("index.html", page="home")


@app.get("/analysis/<analysis_id>")
def analysis_page(analysis_id):
    record = db.get_analysis(Config.DATABASE_PATH, analysis_id, current_uid())
    if not record:
        abort(404)
    return render_template("analysis.html", page="analysis", record=record)


@app.get("/history")
def history_page():
    return render_template("history.html", page="history")


@app.get("/dashboard")
def dashboard_page():
    return render_template("dashboard.html", page="dashboard")


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return _error("Not found", 404)
    return render_template("404.html", page="404"), 404


@app.errorhandler(413)
def too_large(_):
    return _error("That file is larger than 8 MB. Try a smaller screenshot.", 413)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    ready, reason = analyzer.llm.is_ready()
    return jsonify({"ok": True, "provider": Config.AI_PROVIDER, "model": analyzer.llm.label, "ai_ready": ready,
                    "detail": reason, "history_enabled": Config.SAVE_HISTORY})


@app.post("/api/analyze")
def api_analyze():
    """Accepts JSON {text, language} or multipart form with `image` (+ optional `text`, `language`)."""
    source = "text"
    ocr = None

    if request.files.get("image"):
        file = request.files["image"]
        mime = (file.mimetype or "").lower()
        if mime not in Config.ALLOWED_IMAGE_TYPES:
            return _error("Upload a JPG, PNG or WebP screenshot.")
        data = file.read()
        try:
            Image.open(io.BytesIO(data)).verify()  # make sure it's really an image
        except (UnidentifiedImageError, OSError):
            return _error("That file doesn't look like a valid image.")
        try:
            ocr = analyzer.extract_text(data, mime)
        except AIUnavailable as exc:
            return _error(str(exc), 503)
        text = ocr["text"]
        if not text:
            return _error("No readable text was found in the screenshot. Try a clearer image or paste the text.", 422)
        source = "screenshot"
        lang = _lang(request.form.get("language"))
    else:
        payload = request.get_json(silent=True) or request.form
        text = (payload.get("text") or "").strip()
        lang = _lang(payload.get("language"))
        if not text:
            return _error("Paste a message or upload a screenshot to analyse.")

    truncated = len(text) > Config.MAX_MESSAGE_CHARS
    text = text[: Config.MAX_MESSAGE_CHARS]

    result = analyzer.analyze(text, lang)
    if truncated:
        result["notice"] = (result.get("notice", "") + " Only the first "
                            f"{Config.MAX_MESSAGE_CHARS} characters were analysed.").strip()

    analysis_id = None
    if Config.SAVE_HISTORY:
        analysis_id = db.save_analysis(Config.DATABASE_PATH, text, result, source, uid=current_uid(),
                                       redact=Config.REDACT_STORED_MESSAGES)

    return jsonify({
        "ok": True,
        "id": analysis_id,
        "source": source,
        "message": text,
        "ocr": {"notes": ocr["notes"], "engine": ocr["engine"]} if ocr else None,
        "language": lang,
        "result": result,
    })


def _context_from_request():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", ""))[: Config.MAX_MESSAGE_CHARS]
    analysis = payload.get("analysis") or {}
    if not isinstance(analysis, dict) or not analysis:
        abort(400)
    return payload, message, analysis


@app.post("/api/action-plan")
def api_action_plan():
    payload, message, analysis = _context_from_request()
    steps = analyzer.action_plan(message, analysis, _lang(payload.get("language")))
    return jsonify({"ok": True, "steps": steps})


@app.post("/api/eli12")
def api_eli12():
    payload, _, analysis = _context_from_request()
    return jsonify({"ok": True, "explanation": analyzer.eli12(analysis, _lang(payload.get("language")))})


@app.post("/api/family-note")
def api_family_note():
    payload, _, analysis = _context_from_request()
    return jsonify({"ok": True, "note": analyzer.family_note(analysis, _lang(payload.get("language")))})


@app.post("/api/chat")
def api_chat():
    payload, message, analysis = _context_from_request()
    question = str(payload.get("question", "")).strip()[:500]
    if not question:
        return _error("Type a question first.")
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    answer = analyzer.chat(message, analysis, question, history, _lang(payload.get("language")))
    return jsonify({"ok": True, "answer": answer})


@app.get("/api/history")
def api_history():
    return jsonify({"ok": True, "items": db.list_analyses(Config.DATABASE_PATH, uid=current_uid())})


@app.get("/api/history/<analysis_id>")
def api_history_item(analysis_id):
    record = db.get_analysis(Config.DATABASE_PATH, analysis_id, current_uid())
    if not record:
        return _error("Analysis not found", 404)
    return jsonify({"ok": True, "item": record})


@app.delete("/api/history/<analysis_id>")
def api_delete_item(analysis_id):
    if not db.delete_analysis(Config.DATABASE_PATH, analysis_id, current_uid()):
        return _error("Analysis not found", 404)
    return jsonify({"ok": True})


@app.delete("/api/history")
def api_clear_history():
    return jsonify({"ok": True, "deleted": db.clear_history(Config.DATABASE_PATH, current_uid())})


@app.get("/api/stats")
def api_stats():
    stats = db.get_stats(Config.DATABASE_PATH, current_uid())
    stats["recent"] = db.list_analyses(Config.DATABASE_PATH, limit=5, uid=current_uid())
    return jsonify({"ok": True, **stats})


# --------------------------------------------------------------------------- #
# CLI:  flask --app app init-db
# --------------------------------------------------------------------------- #
@app.cli.command("init-db")
def init_db_command():
    """Create the SQLite tables (safe to run more than once)."""
    db.init_db(Config.DATABASE_PATH)
    print(f"Database ready at {Config.DATABASE_PATH}")


if __name__ == "__main__":
    print("\n  ScamShield AI running at http://127.0.0.1:5000")
    ready, reason = analyzer.llm.is_ready()
    print(f"  AI engine: {analyzer.llm.label if ready else 'built-in rule engine'}")
    if not ready:
        print(f"  ({reason})")
    print()
    app.run(debug=True, port=5000)
