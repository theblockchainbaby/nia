"""Thin IMAP helper used by email-related builtins.

Account dict shape:
  {"user": "...", "pass": "...", "server": "...", "sent_folder": "..."}

stdlib-only: imaplib, email, email.header.
"""
from __future__ import annotations

import email as emaillib
import imaplib
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import getaddresses, parsedate_to_datetime
from typing import Iterator


def decode_h(s: str | None) -> str:
    if not s:
        return ""
    try:
        out = []
        for txt, enc in decode_header(s):
            if isinstance(txt, bytes):
                out.append(txt.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(txt)
        return "".join(out)
    except Exception:
        return str(s)


def addr_of(raw: str | None) -> str:
    if not raw:
        return ""
    parsed = getaddresses([raw])
    return (parsed[0][1] or "").lower() if parsed else ""


def msg_date_iso(date_str: str | None) -> str:
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def open_inbox(account: dict, timeout: int = 25) -> imaplib.IMAP4_SSL:
    m = imaplib.IMAP4_SSL(account["server"], 993, timeout=timeout)
    m.login(account["user"], account["pass"])
    return m


def fetch_recent(m: imaplib.IMAP4_SSL, folder: str, since_days: int = 2,
                 max_messages: int = 200) -> Iterator[emaillib.message.Message]:
    """Yield Message objects in `folder` since N days ago (most recent last)."""
    typ, _ = m.select(folder, readonly=True)
    if typ != "OK":
        return
    since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    typ, data = m.search(None, f'(SINCE "{since}")')
    if typ != "OK":
        return
    ids = (data[0] or b"").split()
    for mid in ids[-max_messages:]:
        typ, d = m.fetch(mid, "(BODY.PEEK[HEADER.FIELDS "
                              "(FROM TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO)])")
        if typ != "OK" or not d or not d[0]:
            continue
        raw = d[0][1] if isinstance(d[0], tuple) else b""
        yield emaillib.message_from_bytes(raw)


def fetch_uids_since(m: imaplib.IMAP4_SSL, folder: str, last_uid: int,
                     max_messages: int = 100) -> list[int]:
    """UID-based incremental fetch. last_uid=0 means first run → last 24h only."""
    typ, _ = m.select(folder, readonly=True)
    if typ != "OK":
        return []
    if last_uid:
        typ, data = m.uid("search", None, f"UID {last_uid + 1}:*")
    else:
        since = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
        typ, data = m.uid("search", None, f'(SINCE "{since}")')
    if typ != "OK":
        return []
    uids = (data[0] or b"").split()[-max_messages:]
    return [int(u) for u in uids]


def fetch_by_uid(m: imaplib.IMAP4_SSL, uid: int) -> emaillib.message.Message | None:
    typ, d = m.uid("fetch", str(uid).encode(),
                   "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO)])")
    if typ != "OK" or not d or not d[0]:
        return None
    raw = d[0][1] if isinstance(d[0], tuple) else b""
    return emaillib.message_from_bytes(raw)
