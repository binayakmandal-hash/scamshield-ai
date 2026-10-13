"""Routes for the four safety tools: chat check, UPI check, call copilot and golden hour."""
import io
import zipfile

from flask import Blueprint, jsonify, render_template, request
from PIL import Image, UnidentifiedImageError

from services import call_tactics, payment_receipt, upi_check
from services.ai_analyzer import AIUnavailable

MAX_CHAT_CHARS = 200_000  # a long WhatsApp export is fine; the tracker only reads text
VALID_LANGS = {"en", "hi", "bn"}


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _lang(value) -> str:
    return value if value in VALID_LANGS else "en"


def _read_chat_upload(file) -> str:
    """A WhatsApp export is a .txt, or a .zip holding one (iOS: _chat.txt). Returns the text, or raises ValueError."""
    name = (file.filename or "").lower()
    data = file.read(8 * 1024 * 1024 + 1)
    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                txts = [i for i in zf.infolist() if i.filename.lower().endswith(".txt") and i.file_size < 20 * 1024 * 1024]
                if not txts:
                    raise ValueError("That .zip has no chat .txt file inside. Export the chat 'without media' and try again.")
                txts.sort(key=lambda i: (not i.filename.lower().endswith("_chat.txt"), -i.file_size))
                data = zf.read(txts[0])
        except zipfile.BadZipFile as exc:
            raise ValueError("That .zip file couldn't be opened.") from exc
    elif not name.endswith(".txt"):
        raise ValueError("Upload the chat as a .txt file (WhatsApp: ⋮ → More → Export chat → Without media), or paste it.")
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("Couldn't read that file as text.")


def create_blueprint(config, analyzer) -> Blueprint:
    bp = Blueprint("tools", __name__)

    def read_image():
        """Validated image bytes and mime from request.files['image'], or (None, None). Raises ValueError on a bad file."""
        file = request.files.get("image")
        if not file:
            return None, None
        mime = (file.mimetype or "").lower()
        if mime not in config.ALLOWED_IMAGE_TYPES:
            raise ValueError("Upload a JPG, PNG or WebP image.")
        data = file.read()
        try:
            Image.open(io.BytesIO(data)).verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("That file doesn't look like a valid image.") from exc
        return data, mime

    def ocr(data, mime):
        """Text from an image, or ('', note) when no OCR engine is available."""
        try:
            out = analyzer.extract_text(data, mime)
            return out["text"], out.get("engine")
        except AIUnavailable:
            return "", None

    # ------------------------------------------------------------- pages
    @bp.get("/chat-check")
    def chat_check_page():
        return render_template("chat_check.html", page="chat")

    @bp.get("/upi-check")
    def upi_check_page():
        return render_template("upi_check.html", page="upi")

    @bp.get("/call-copilot")
    def call_copilot_page():
        return render_template("call_copilot.html", page="call", tactics=call_tactics.for_client())

    @bp.get("/paid")
    def golden_hour_page():
        return render_template("golden_hour.html", page="paid")

    # --------------------------------------------------------------- API
    @bp.post("/api/chat-check")
    def api_chat_check():
        if request.files.get("chat"):
            try:
                raw = _read_chat_upload(request.files["chat"])
            except ValueError as exc:
                return _error(str(exc))
        else:
            payload = request.get_json(silent=True) or request.form
            raw = str(payload.get("text") or "")
        if not raw.strip():
            return _error("Paste the conversation or upload a WhatsApp export first.")
        truncated = len(raw) > MAX_CHAT_CHARS
        result = analyzer.script_check(raw[:MAX_CHAT_CHARS])
        if truncated:
            result["notice"] = "This chat is very long, so only the first part was checked."
        return jsonify({"ok": True, "result": result})

    @bp.post("/api/upi-check")
    def api_upi_check():
        try:
            data, mime = read_image()
        except ValueError as exc:
            return _error(str(exc))
        form = request.form if (request.files or request.form) else (request.get_json(silent=True) or {})
        text = str(form.get("text") or "")[: config.MAX_MESSAGE_CHARS]
        lang = _lang(form.get("language"))
        if not data and not text.strip():
            return _error("Upload a QR code or payment screenshot, or paste the message.")
        qr, ocr_text, engine = [], "", None
        if data:
            qr = upi_check.decode_qr(data)
            ocr_text, engine = ocr(data, mime)
            if not qr and not ocr_text and not text.strip():
                return _error("We couldn't read a QR code or any text in that image. Try a sharper screenshot, or paste the text.", 422)
        result = upi_check.check((text + "\n" + ocr_text).strip(), qr, lang)
        result["ocr_engine"] = engine
        return jsonify({"ok": True, "result": result})

    @bp.get("/api/call-tactics")
    def api_call_tactics():
        return jsonify({"ok": True, "tactics": call_tactics.for_client()})

    @bp.post("/api/paid/extract")
    def api_paid_extract():
        try:
            data, mime = read_image()
        except ValueError as exc:
            return _error(str(exc))
        form = request.form if (request.files or request.form) else (request.get_json(silent=True) or {})
        text = str(form.get("text") or "")[: config.MAX_MESSAGE_CHARS]
        engine = None
        if data:
            ocr_text, engine = ocr(data, mime)
            if not ocr_text and not text.strip():
                return _error("We couldn't read text in that screenshot. Type the details in by hand; it only takes a minute.", 422)
            text = (text + "\n" + ocr_text).strip()
        if not text.strip():
            return _error("Upload the payment screenshot or paste the bank SMS.")
        out = payment_receipt.extract(text)
        out["ocr_engine"] = engine
        return jsonify({"ok": True, **out})

    return bp
