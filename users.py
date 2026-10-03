"""Who is the current user?

Locally (PUBLIC_MODE=false) there is one user, "local", so the app behaves
like a personal desktop tool. In PUBLIC_MODE (a deployed website) every
browser session gets its own random id, which keeps each visitor's Gmail
sign-in, history, learning and demo inbox separate from everyone else's.
"""
import re
import secrets

from flask import has_request_context, session

from config import Config
from database import LOCAL

_UID_RE = re.compile(r"^[0-9a-f]{32}$")


def current_uid() -> str:
    if not Config.PUBLIC_MODE or not has_request_context():
        return LOCAL
    uid = session.get("uid")
    if not uid or not _UID_RE.match(uid):
        uid = secrets.token_hex(16)
        session["uid"] = uid
        session.permanent = True
    return uid
