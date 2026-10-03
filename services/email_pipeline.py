"""Scoring for emails: the message analysis plus email-only signals.

Extra signals (each shown as its own line in "How the score was built"):
  + sender failed DMARC authentication        (from Gmail's Authentication-Results header)
  + similar to emails you marked as scams     (the learner)
  - verified sender from an organisation's official domain
  - a sender you marked as safe
"""
from . import rule_engine
from .brands import BRANDS, is_official_domain
from .rule_engine import level_for
from .schema import normalize_analysis
from .sender_analyzer import FREE_EMAIL_PROVIDERS, analyze_sender
from .url_analyzer import analyze_urls


def email_text(mail: dict) -> str:
    """The text that gets analysed: headers, body, and the real targets of any links."""
    body = mail.get("body") or mail.get("snippet") or ""
    lines = [f"From: {mail.get('from_name', '')} <{mail.get('from_email', '')}>",
             f"Subject: {mail.get('subject', '')}", "", body]
    hidden = [link for link in mail.get("links", []) if link not in body]
    if hidden:
        lines += ["", "Links in this email:"] + hidden[:15]
    return "\n".join(lines)[:8000]


def _official_brand(domain: str):
    for brand in BRANDS:
        if is_official_domain(brand, domain):
            return brand["name"]
    return None


def _signal(result, title, points, evidence, explanation, severity="medium", flag=True):
    result["score_breakdown"].append({"signal": title, "points": points, "evidence": evidence,
                                      "evidence_verified": None})
    if flag:
        result["red_flags"].append({"title": title, "evidence": evidence, "explanation": explanation,
                                    "severity": severity, "evidence_verified": None})
    else:
        result.setdefault("trust_signals", []).append({"title": title, "evidence": evidence,
                                                       "explanation": explanation})


def enrich(result: dict, mail: dict, learner, sender_rule) -> dict:
    """Add email-only signals and recompute the score so it stays the sum of the breakdown."""
    text = email_text(mail)
    sender = mail.get("from_email", "")
    domain = sender.split("@", 1)[1] if "@" in sender else ""
    auth = mail.get("auth") or {}
    result.setdefault("score_breakdown", [])
    result.setdefault("red_flags", [])

    # 1. Sender authentication (headers added by Gmail itself)
    if auth.get("dmarc") == "fail":
        _signal(result, "Sender verification failed", 20, f"DMARC: fail for {domain}",
                "Gmail could not confirm that this email really came from the domain in the From address. "
                "This is common in spoofed emails, though misconfigured senders can also fail.", "high")
    elif auth.get("spf") == "fail" and auth.get("dkim") in ("fail", None):
        _signal(result, "Sender verification failed", 10, f"SPF: fail for {domain}",
                "The sending server isn't authorised to send email for this domain.", "medium")

    # Anyone can get a gmail.com / outlook.com address, so free providers never count as "verified".
    brand = _official_brand(domain) if domain and domain not in FREE_EMAIL_PROVIDERS else None
    verified = auth.get("dmarc") == "pass" or (auth.get("dkim") == "pass" and auth.get("spf") == "pass")
    if brand and verified:
        _signal(result, f"Verified sender from {brand}", -20, f"{domain} (DMARC/DKIM pass)",
                f"The email passed Gmail's authentication checks and comes from an official {brand} domain.", flag=False)

    # 2. The learner
    prob, words = learner.predict(text, sender) if learner else (None, [])
    result["learning"] = {"probability": None if prob is None else round(prob, 3), "words": words}
    if prob is not None and prob >= 0.7:
        pts = min(20, round((prob - 0.5) * 40))
        n = learner.stats.get("total_examples", 0)
        fb = learner.stats.get("feedback", {})
        mine = " including your feedback" if fb.get("scam", 0) + fb.get("safe", 0) else ""
        _signal(result, "Similar to emails marked as scams", pts,
                ", ".join(words) if words else mail.get("subject", ""),
                f"ScamShield's learning model (trained on {n} examples{mine}) rates this email "
                f"{min(99, round(prob * 100))}% similar to known scams. It is a pattern match, not proof.", "medium")

    # 3. Your sender rules
    if sender_rule and sender_rule.get("kind") == "trusted":
        _signal(result, "You marked this sender as safe", -40, sender,
                "You told ScamShield this sender is safe, so its score is lowered. You can undo this any time.",
                flag=False)
    elif sender_rule and sender_rule.get("kind") == "blocked":
        _signal(result, "You blocked this sender", 30, sender, "You previously blocked this sender.", "high")

    result.setdefault("sender_analysis", {})["auth"] = auth
    score = max(0, min(100, sum(b["points"] for b in result["score_breakdown"])))
    result["risk_score"] = score
    result["risk_level"] = level_for(score)
    return result


def quick_analyze(mail: dict, learner, sender_rule) -> dict:
    """Fast, offline analysis used to score a whole inbox at once."""
    text = email_text(mail)
    urls, sender = analyze_urls(text), analyze_sender(text)
    result = normalize_analysis(rule_engine.analyze(text, urls, sender, strict_links=True), text)
    result.update(engine="rules", detected_urls=urls, sender_analysis=sender)
    return enrich(result, mail, learner, sender_rule)


def deep_analyze(mail: dict, analyzer, learner, sender_rule, lang="en") -> dict:
    """Full analysis with the AI model (falls back to rules), plus email signals."""
    result = analyzer.analyze(email_text(mail), lang, strict_links=True)
    return enrich(result, mail, learner, sender_rule)


def summary_row(mail: dict, result: dict, sender_rule) -> dict:
    return {
        "id": mail["id"], "from_name": mail.get("from_name"), "from_email": mail.get("from_email"),
        "subject": mail.get("subject"), "date": mail.get("date"), "timestamp": mail.get("timestamp"),
        "snippet": (mail.get("snippet") or "")[:180],
        "risk_score": result["risk_score"], "risk_level": result["risk_level"],
        "categories": result.get("categories", [])[:2],
        "flags": [f["title"] for f in result.get("red_flags", [])][:3],
        "sender_rule": sender_rule.get("kind") if sender_rule else None,
        "auth": mail.get("auth") or {},
    }
