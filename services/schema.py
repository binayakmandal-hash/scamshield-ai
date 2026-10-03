"""Validate and normalise analysis JSON before it reaches the UI.

The AI's output is never trusted blindly:
  * unknown fields are dropped, missing ones get safe defaults
  * every evidence quote is checked against the original message
  * the score is recomputed from the breakdown so it is never arbitrary
  * the risk level is derived from the score so the two always agree
"""
import json
import re

from .prompt_builder import CATEGORIES
from .rule_engine import level_for

_CATEGORY_LOOKUP = {c.lower(): c for c in CATEGORIES}
_SEVERITIES = {"low", "medium", "high"}
_ABSOLUTE = re.compile(r"\b(definitely|certainly|100%|guaranteed to be|for sure)\b", re.I)


class AnalysisFormatError(ValueError):
    """Raised when the AI response cannot be turned into a valid analysis."""


def extract_json(raw: str) -> dict:
    """Parse JSON from a model response, tolerating code fences or stray text."""
    if isinstance(raw, dict):
        return raw
    if not raw or not raw.strip():
        raise AnalysisFormatError("Empty response from AI")
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                raise AnalysisFormatError(f"Malformed JSON from AI: {exc}") from exc
        raise AnalysisFormatError("No JSON object found in AI response")


def _str(value, limit=600) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _soften(text: str) -> str:
    """Replace absolute claims the model may have slipped in."""
    return _ABSOLUTE.sub("likely", text)


def evidence_in_message(evidence: str, message: str) -> bool:
    if not evidence:
        return False
    pattern = r"\s+".join(re.escape(part) for part in evidence.split())
    return bool(re.search(pattern, message, re.I))


def _int(value, lo, hi, default=0) -> int:
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def normalize_analysis(data: dict, message: str) -> dict:
    if not isinstance(data, dict):
        raise AnalysisFormatError("AI response is not a JSON object")
    if "red_flags" not in data and "risk_score" not in data:
        raise AnalysisFormatError("AI response is missing required fields")

    # --- red flags -----------------------------------------------------------
    red_flags = []
    for f in (data.get("red_flags") or [])[:12]:
        if not isinstance(f, dict):
            continue
        title = _str(f.get("title"), 80)
        if not title:
            continue
        evidence = _str(f.get("evidence"), 300).strip("\"'“”")
        sev = _str(f.get("severity"), 10).lower()
        red_flags.append({
            "title": title,
            "evidence": evidence,
            "explanation": _soften(_str(f.get("explanation"), 500)),
            "severity": sev if sev in _SEVERITIES else "medium",
            "evidence_verified": evidence_in_message(evidence, message),
        })

    # --- score breakdown -----------------------------------------------------
    breakdown = []
    for b in (data.get("score_breakdown") or [])[:12]:
        if not isinstance(b, dict):
            continue
        signal = _str(b.get("signal"), 80)
        points = _int(b.get("points"), 0, 40)
        if not signal or points == 0:
            continue
        evidence = _str(b.get("evidence"), 300).strip("\"'“”")
        verified = evidence_in_message(evidence, message)
        # Signals with no verifiable evidence count for half - they're inferences, not observations.
        if evidence and not verified:
            points = max(1, points // 2)
        breakdown.append({"signal": signal, "points": points, "evidence": evidence, "evidence_verified": verified})

    if breakdown:
        score = min(100, sum(b["points"] for b in breakdown))
    else:
        score = _int(data.get("risk_score"), 0, 100)
        if red_flags and score == 0:
            score = min(100, 10 * len(red_flags))

    categories = []
    for c in data.get("categories") or []:
        canon = _CATEGORY_LOOKUP.get(_str(c, 60).lower())
        if canon and canon not in categories:
            categories.append(canon)

    actions = [_soften(_str(a, 300)) for a in (data.get("recommended_actions") or []) if _str(a)][:6]
    # Hard safety filter: never pass through advice to open/click links.
    actions = [a for a in actions if not re.search(r"\b(click|open|visit|tap)\b.*\blink\b", a, re.I)
               or re.search(r"\b(don't|do not|never|avoid)\b", a, re.I)]

    return {
        "risk_score": score,
        "risk_level": level_for(score),
        "categories": categories,
        "summary": _soften(_str(data.get("summary"), 700)),
        "red_flags": red_flags,
        "score_breakdown": breakdown,
        "why_it_matters": _soften(_str(data.get("why_it_matters"), 1200)),
        "recommended_actions": actions,
        "confidence_note": _soften(_str(data.get("confidence_note"), 400)) or
        "This analysis is based on warning signs in the text and is not proof that the message is fraudulent.",
        "language": _str(data.get("language"), 40) or "auto",
    }
