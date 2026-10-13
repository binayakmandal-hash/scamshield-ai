"""Open-weight LLM clients plus the analysis pipeline.

Pipeline for one message:
    text -> safe URL scan + sender scan (deterministic, never opens links)
         -> open-weight model, e.g. Gemma 4 via Ollama (structured JSON)
            or the rule engine (offline fallback)
         -> schema validation (evidence check, score recomputed)
         -> merged result for the UI

By default everything runs on your own machine: the message, the screenshot
and the model never leave it. No proprietary AI API is required.
"""
import base64
import logging
import time

import requests

from . import prompt_builder as prompts
from . import rule_engine
from . import scam_scripts
from .schema import AnalysisFormatError, extract_json, normalize_analysis
from .sender_analyzer import analyze_sender
from .url_analyzer import analyze_urls

log = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    """The model could not be reached or returned something unusable."""


# --------------------------------------------------------------------------- #
# Clients - each exposes: enabled, label, is_ready(), generate_json(...)
# --------------------------------------------------------------------------- #
class _BaseClient:
    label = "Rule engine"
    enabled = False

    def __init__(self, timeout: int = 180):
        self.timeout = timeout
        self._ready_cache = (0.0, False, "")

    def is_ready(self):
        """(ready, reason) - cached for 30 s so pages stay fast."""
        checked_at, ready, reason = self._ready_cache
        if time.time() - checked_at > 30:
            ready, reason = self._probe()
            self._ready_cache = (time.time(), ready, reason)
        return ready, reason

    def _probe(self):
        return False, "No AI provider configured"

    def _call(self, system, prompt, image, mime, temperature) -> str:
        raise AIUnavailable("No AI provider configured")

    def generate_json(self, prompt: str, system: str = None, image: bytes = None, mime: str = None,
                      temperature: float = 0.2, retries: int = 1) -> dict:
        if not self.enabled:
            raise AIUnavailable("No AI provider configured")
        last_error = None
        for _ in range(retries + 1):
            try:
                return extract_json(self._call(system, prompt, image, mime, temperature))
            except AnalysisFormatError as exc:  # malformed JSON -> retry once
                last_error = exc
                log.warning("Malformed JSON from %s, retrying: %s", self.label, exc)
            except requests.RequestException as exc:
                self._ready_cache = (time.time(), False, str(exc))
                raise AIUnavailable(f"Could not reach {self.label}: {exc}") from exc
        raise AIUnavailable(f"{self.label} returned malformed JSON twice: {last_error}")


class NoAIClient(_BaseClient):
    pass


class OllamaClient(_BaseClient):
    """Local inference through Ollama (https://ollama.com). Default model: Gemma 4."""

    enabled = True

    def __init__(self, host: str, model: str, timeout: int = 180):
        super().__init__(timeout)
        self.host = host
        self.model = model
        self.label = f"{model} (local)"

    def _probe(self):
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            names = {m.get("name", "") for m in resp.json().get("models", [])}
        except (requests.RequestException, ValueError):
            return False, f"Ollama isn't running at {self.host}. Start it, or the rule engine will be used."
        wanted = self.model if ":" in self.model else self.model + ":latest"
        if wanted not in names and self.model not in names:
            return False, f"Model {self.model} isn't downloaded yet. Run: ollama pull {self.model}"
        return True, "ready"

    def _call(self, system, prompt, image, mime, temperature) -> str:
        user = {"role": "user", "content": prompt}
        if image is not None:
            user["images"] = [base64.b64encode(image).decode()]
        messages = ([{"role": "system", "content": system}] if system else []) + [user]
        resp = requests.post(
            f"{self.host}/api/chat",
            json={"model": self.model, "messages": messages, "format": "json", "stream": False,
                  "options": {"temperature": temperature}},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise AIUnavailable(f"Ollama error {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("message", {}).get("content", "")


class OpenAICompatibleClient(_BaseClient):
    """Any OpenAI-compatible /chat/completions server hosting an open-weight model."""

    enabled = True

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180):
        super().__init__(timeout)
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.label = model
        self._json_mode = True
        if not (base_url and model):
            self.enabled = False

    def _probe(self):
        if not self.enabled:
            return False, "Set OPENAI_BASE_URL and OPENAI_MODEL in .env"
        return True, "configured"

    def _call(self, system, prompt, image, mime, temperature) -> str:
        content = [{"type": "text", "text": prompt}]
        if image is not None:
            content.insert(0, {"type": "image_url",
                               "image_url": {"url": f"data:{mime};base64,{base64.b64encode(image).decode()}"}})
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]
        body = {"model": self.model, "messages": messages, "temperature": temperature}
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        if resp.status_code == 400 and self._json_mode:
            # Some servers don't support JSON mode; the prompt already asks for JSON.
            self._json_mode = False
            return self._call(system, prompt, image, mime, temperature)
        if resp.status_code != 200:
            raise AIUnavailable(f"Model server error {resp.status_code}: {resp.text[:200]}")
        return resp.json()["choices"][0]["message"]["content"] or ""


def build_client(config) -> _BaseClient:
    if config.AI_PROVIDER == "ollama":
        return OllamaClient(config.OLLAMA_HOST, config.OLLAMA_MODEL, config.AI_TIMEOUT)
    if config.AI_PROVIDER == "openai":
        return OpenAICompatibleClient(config.OPENAI_BASE_URL, config.OPENAI_API_KEY, config.OPENAI_MODEL,
                                      config.AI_TIMEOUT)
    return NoAIClient()


# --------------------------------------------------------------------------- #
# Service used by the Flask routes
# --------------------------------------------------------------------------- #
class ScamAnalyzer:
    def __init__(self, llm: _BaseClient):
        self.llm = llm

    def _ai_ready(self) -> bool:
        return self.llm.enabled and self.llm.is_ready()[0]

    # ------------------------------------------------------------------ OCR
    def extract_text(self, image: bytes, mime: str) -> dict:
        if self._ai_ready():
            try:
                data = self.llm.generate_json("Transcribe the message in this screenshot.",
                                              system=prompts.OCR_SYSTEM, image=image, mime=mime, temperature=0)
                return {"text": str(data.get("text", "")).strip(), "notes": str(data.get("notes", "") or ""),
                        "contains_message": bool(data.get("contains_message", True)), "engine": "ai"}
            except AIUnavailable as exc:
                log.warning("Model OCR failed, trying Tesseract: %s", exc)
        return self._tesseract(image)

    @staticmethod
    def _tesseract(image: bytes) -> dict:
        try:
            import io

            import pytesseract
            from PIL import Image

            text = pytesseract.image_to_string(Image.open(io.BytesIO(image)), lang="eng+hin+ben")
        except Exception:
            try:
                import io

                import pytesseract
                from PIL import Image

                text = pytesseract.image_to_string(Image.open(io.BytesIO(image)), lang="eng")
            except Exception as exc:  # pytesseract or the tesseract binary not installed
                raise AIUnavailable(
                    "Reading screenshots needs a vision model (e.g. `ollama pull gemma4:e4b` with Ollama running) "
                    "or Tesseract OCR installed. You can paste the message text instead."
                ) from exc
        return {"text": text.strip(), "notes": "Extracted with offline OCR (Tesseract).",
                "contains_message": bool(text.strip()), "engine": "tesseract"}

    # ------------------------------------------------------------- analysis
    def analyze(self, message: str, lang: str = "en", strict_links: bool = False) -> dict:
        urls = analyze_urls(message)
        sender = analyze_sender(message)
        notice = None
        result = None

        if self.llm.enabled:
            ready, reason = self.llm.is_ready()
            if ready:
                try:
                    raw = self.llm.generate_json(prompts.build_analysis_prompt(message, urls, sender, lang),
                                                 system=prompts.ANALYSIS_SYSTEM)
                    result = normalize_analysis(raw, message)
                    result["engine"] = "ai"
                    result["model"] = self.llm.label
                except (AIUnavailable, AnalysisFormatError) as exc:
                    log.warning("Falling back to rule engine: %s", exc)
                    notice = "The AI model didn't respond in time, so this analysis uses ScamShield's built-in rule engine."
            else:
                notice = f"{reason} This analysis uses ScamShield's built-in rule engine."

        if result is None:
            result = normalize_analysis(rule_engine.analyze(message, urls, sender, strict_links), message)
            result["engine"] = "rules"
            if lang in ("hi", "bn"):
                notice = ((notice or "") + " Hindi and Bengali explanations need the AI model, so this one is in English.").strip()

        # Deterministic facts always come from our own safe checks.
        result["detected_urls"] = urls
        result["sender_analysis"] = sender
        if notice:
            result["notice"] = notice
        return result

    # ---------------------------------------------------------- follow-ups
    def _try(self, build_prompt, parse, temperature=0.4):
        if not self._ai_ready():
            return None
        try:
            return parse(self.llm.generate_json(build_prompt(), system=prompts.SAFETY_RULES, temperature=temperature))
        except (AIUnavailable, AnalysisFormatError, AttributeError, TypeError) as exc:
            log.warning("Follow-up fell back to rules: %s", exc)
            return None

    def action_plan(self, message: str, analysis: dict, lang: str = "en") -> list:
        def parse(data):
            steps = [{"title": str(s.get("title", "")).strip()[:60], "detail": str(s.get("detail", "")).strip()[:400]}
                     for s in data.get("steps", []) if isinstance(s, dict)]
            steps = [s for s in steps if s["title"] and s["detail"]]
            return steps[:3] if len(steps) >= 3 else None

        return self._try(lambda: prompts.build_action_plan_prompt(message, analysis, lang), parse, 0.3) \
            or rule_engine.action_plan(analysis)

    def eli12(self, analysis: dict, lang: str = "en") -> str:
        return self._try(lambda: prompts.build_eli12_prompt(analysis, lang),
                         lambda d: str(d.get("explanation", "")).strip()[:1500] or None, 0.5) \
            or rule_engine.eli12(analysis)

    def family_note(self, analysis: dict, lang: str = "en") -> str:
        return self._try(lambda: prompts.build_family_note_prompt(analysis, lang),
                         lambda d: str(d.get("note", "")).strip()[:800] or None, 0.5) \
            or rule_engine.family_note(analysis, lang)

    def chat(self, message: str, analysis: dict, question: str, history: list, lang: str = "en") -> str:
        if self._ai_ready():
            try:
                data = self.llm.generate_json(
                    prompts.build_chat_prompt(message, analysis, question, history, lang), temperature=0.4)
                answer = str(data.get("answer", "")).strip()
                if answer:
                    return answer[:2000]
            except (AIUnavailable, AnalysisFormatError) as exc:
                log.warning("Chat fallback: %s", exc)
        return rule_engine.chat_answer(question, analysis)

    # ------------------------------------------------------- script tracker
    def script_check(self, raw_chat: str) -> dict:
        """Which scam script does this conversation follow, and what comes next? Rules first, AI as a checked second opinion."""
        result = scam_scripts.track(raw_chat)
        if result.get("messages") and self._ai_ready():
            try:
                ai = self.llm.generate_json(
                    prompts.build_script_prompt(scam_scripts.parse_chat(raw_chat), scam_scripts.library()),
                    system=prompts.SAFETY_RULES, temperature=0.1)
                result = scam_scripts.apply_ai(result, ai, raw_chat)
            except (AIUnavailable, AnalysisFormatError) as exc:
                log.warning("Script check fell back to rules: %s", exc)
        return result
