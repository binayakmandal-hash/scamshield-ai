"""Gmail access through Google's REST API (OAuth 2.0), using only `requests`.

What ScamShield can do with your permission:
  * read inbox messages              (gmail.modify)
  * move to Spam / Trash and back    (gmail.modify)
  * block a sender with a filter     (gmail.settings.basic)

The token is stored only on this computer (gmail_token.json, git-ignored).
Disconnecting revokes it at Google and deletes the file.
Links inside emails are never opened.
"""
import base64
import html
import json
import os
import re
import time
from email.utils import parseaddr
from html.parser import HTMLParser
from urllib.parse import urlencode

import requests

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
BLOCK_LABEL = "ScamShield/Blocked"


class GmailError(RuntimeError):
    """Something went wrong talking to Gmail; the message is safe to show to the user."""


# --------------------------------------------------------------------------- #
# Message parsing
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    """HTML -> readable text, plus the real destinations of every link."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self._skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if href.lower().startswith(("http://", "https://")):
                self.links.append(href)
        if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw_html: str):
    parser = _TextExtractor()
    try:
        parser.feed(raw_html)
    except Exception:  # malformed HTML: fall back to stripping tags
        return re.sub(r"<[^>]+>", " ", raw_html), []
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip(), parser.links


def _decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _walk(part, plain, rich):
    mime = part.get("mimeType", "")
    data = part.get("body", {}).get("data")
    if mime == "text/plain" and data:
        plain.append(_decode(data))
    elif mime == "text/html" and data:
        rich.append(_decode(data))
    for sub in part.get("parts", []) or []:
        _walk(sub, plain, rich)


def parse_auth_results(value: str) -> dict:
    """Read SPF / DKIM / DMARC verdicts from the Authentication-Results header."""
    out = {}
    for key in ("spf", "dkim", "dmarc"):
        m = re.search(rf"\b{key}=(\w+)", value or "", re.I)
        out[key] = m.group(1).lower() if m else None
    return out


def parse_message(msg: dict) -> dict:
    payload = msg.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    name, address = parseaddr(headers.get("from", ""))
    plain, rich = [], []
    _walk(payload, plain, rich)

    links = []
    if plain:
        body = "\n".join(plain)
        for r in rich:  # still collect real link targets hidden behind HTML anchors
            links += html_to_text(r)[1]
    elif rich:
        body, links = html_to_text("\n".join(rich))
    else:
        body = msg.get("snippet", "")

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "from_name": name or address,
        "from_email": address.lower(),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "timestamp": int(msg.get("internalDate", "0") or 0) // 1000,
        "snippet": html.unescape(msg.get("snippet", "")),
        "body": body.strip()[:12000],
        "links": list(dict.fromkeys(links))[:20],
        "auth": parse_auth_results(headers.get("authentication-results", "")),
        "list_unsubscribe": bool(headers.get("list-unsubscribe")),
        "labels": msg.get("labelIds", []),
    }


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class GmailClient:
    def __init__(self, config, token_file: str = None):
        self.redirect_uri = config.GMAIL_REDIRECT_URI
        self.token_file = token_file or config.GMAIL_TOKEN_FILE
        self.client_id = config.GOOGLE_CLIENT_ID
        self.client_secret = config.GOOGLE_CLIENT_SECRET
        path = config.GOOGLE_CLIENT_SECRETS_FILE
        if (not self.client_id) and path and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            info = data.get("web") or data.get("installed") or {}
            self.client_id = info.get("client_id", "")
            self.client_secret = info.get("client_secret", "")
        self._label_id = None

    # ------------------------------------------------------------ OAuth
    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def connected(self) -> bool:
        return os.path.exists(self.token_file)

    def auth_url(self, state: str) -> str:
        return AUTH_URL + "?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
            "include_granted_scopes": "true", "state": state,
        })

    def exchange_code(self, code: str) -> None:
        resp = requests.post(TOKEN_URL, data={
            "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri, "grant_type": "authorization_code",
        }, timeout=20)
        if resp.status_code != 200:
            raise GmailError(f"Google sign-in failed: {resp.json().get('error_description', resp.text[:200])}")
        self._save_token(resp.json())

    def _save_token(self, data: dict, old: dict = None) -> dict:
        os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
        token = dict(old or {})
        token["access_token"] = data["access_token"]
        token["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        if data.get("refresh_token"):
            token["refresh_token"] = data["refresh_token"]
        with open(self.token_file, "w", encoding="utf-8") as fh:
            json.dump(token, fh)
        return token

    def _token(self) -> str:
        if not self.connected:
            raise GmailError("Gmail isn't connected yet.")
        with open(self.token_file, encoding="utf-8") as fh:
            token = json.load(fh)
        if token.get("expires_at", 0) - 60 < time.time():
            token = self._refresh(token)
        return token["access_token"]

    def _refresh(self, token: dict) -> dict:
        if not token.get("refresh_token"):
            raise GmailError("Your Gmail session expired. Connect Gmail again.")
        resp = requests.post(TOKEN_URL, data={
            "client_id": self.client_id, "client_secret": self.client_secret,
            "refresh_token": token["refresh_token"], "grant_type": "refresh_token",
        }, timeout=20)
        if resp.status_code != 200:
            os.remove(self.token_file)
            raise GmailError("Your Gmail session expired or was revoked. Connect Gmail again.")
        return self._save_token(resp.json(), token)

    def disconnect(self) -> None:
        if not self.connected:
            return
        try:
            with open(self.token_file, encoding="utf-8") as fh:
                token = json.load(fh)
            requests.post(REVOKE_URL, params={"token": token.get("refresh_token") or token.get("access_token")},
                          timeout=10)
        except (OSError, ValueError, requests.RequestException):
            pass
        os.remove(self.token_file)

    # ------------------------------------------------------------ requests
    def _req(self, method: str, path: str, **kwargs) -> dict:
        try:
            resp = requests.request(method, API + path, headers={"Authorization": f"Bearer {self._token()}"},
                                    timeout=30, **kwargs)
        except requests.RequestException as exc:
            raise GmailError(f"Couldn't reach Gmail: {exc}") from exc
        if resp.status_code == 401:
            raise GmailError("Gmail rejected the sign-in. Disconnect and connect Gmail again.")
        if resp.status_code == 403:
            msg = resp.json().get("error", {}).get("message", "") if resp.content else ""
            raise GmailError(f"Gmail refused this action (403). {msg}".strip())
        if resp.status_code >= 400:
            msg = resp.json().get("error", {}).get("message", resp.text[:200]) if resp.content else ""
            raise GmailError(f"Gmail error {resp.status_code}: {msg}")
        return resp.json() if resp.content else {}

    def profile(self) -> dict:
        return self._req("GET", "/profile")

    def list_messages(self, limit: int = 25, query: str = "in:inbox") -> list:
        data = self._req("GET", "/messages", params={"maxResults": max(1, min(limit, 100)), "q": query})
        return [m["id"] for m in data.get("messages", [])]

    def get_message(self, message_id: str) -> dict:
        return parse_message(self._req("GET", f"/messages/{message_id}", params={"format": "full"}))

    # ------------------------------------------------------------ actions (all reversible)
    def move_to_spam(self, message_id):
        self._req("POST", f"/messages/{message_id}/modify", json={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]})

    def restore_to_inbox(self, message_id):
        self._req("POST", f"/messages/{message_id}/modify", json={"addLabelIds": ["INBOX"], "removeLabelIds": ["SPAM"]})

    def trash(self, message_id):
        self._req("POST", f"/messages/{message_id}/trash")

    def untrash(self, message_id):
        self._req("POST", f"/messages/{message_id}/untrash")
        self.restore_to_inbox(message_id)

    def _blocked_label(self) -> str:
        if self._label_id:
            return self._label_id
        for label in self._req("GET", "/labels").get("labels", []):
            if label.get("name") == BLOCK_LABEL:
                self._label_id = label["id"]
                return self._label_id
        self._label_id = self._req("POST", "/labels", json={"name": BLOCK_LABEL})["id"]
        return self._label_id

    def block_sender(self, address: str) -> str:
        """Create a filter so future mail from this sender skips the inbox. Returns the filter id."""
        criteria = {"from": address}
        try:  # same as Gmail's own "Block sender": future mail goes to Trash
            created = self._req("POST", "/settings/filters", json={"criteria": criteria,
                                                                   "action": {"addLabelIds": ["TRASH"]}})
        except GmailError:  # fallback: label it and keep it out of the inbox
            created = self._req("POST", "/settings/filters", json={
                "criteria": criteria,
                "action": {"addLabelIds": [self._blocked_label()], "removeLabelIds": ["INBOX", "UNREAD"]}})
        return created.get("id", "")

    def unblock_sender(self, filter_id: str):
        if filter_id:
            self._req("DELETE", f"/settings/filters/{filter_id}")
