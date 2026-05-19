"""iMessage delivery — macOS only.

Hybrid path discovered the hard way:
  - **Text messages** go through AppleScript reliably.
  - **File attachments** are silently dropped by AppleScript on macOS
    Sonoma/Sequoia; Apple closed that door against automation.
  - The replacement for attachments is a macOS Shortcut invoked via the
    `shortcuts` CLI. Apple's first-party Shortcuts framework uses the
    proper Messages APIs and actually delivers files.

The user creates a Shortcut once (see docs/imessage-setup.md) that takes a
File as input and sends it to a fixed recipient. We call that Shortcut by
name with `shortcuts run "<name>" -i <file>`.
"""
from __future__ import annotations

import os
import subprocess
import sys


def send_pdf(*, inputs: dict, context: dict) -> dict:
    """Send a PDF via iMessage. Text via AppleScript, file via Shortcuts.

    Inputs:
      pdf_path:      filesystem path to the file to send
      to:            phone number or email (e.g., "+15551234567")
      body:          optional text accompanying the file
      shortcut_name: name of the macOS Shortcut that sends a file to `to`.
                     Required — the Shortcuts CLI is the only reliable path
                     for attachments on modern macOS. See docs/imessage-setup.md.

    Returns: {"sent": bool, "to": "...", "pdf_path": "..."}
    """
    pdf_path = os.path.expanduser(str(inputs.get("pdf_path", "")))
    to = str(inputs.get("to", "")).strip()
    body = str(inputs.get("body", "") or "").strip()
    shortcut_name = str(inputs.get("shortcut_name", "") or "").strip()

    if not pdf_path or not to:
        return {"sent": False, "error": "pdf_path and to are required"}

    if context.get("dry_run"):
        return {"sent": False, "dry_run": True, "to": to, "pdf_path": pdf_path,
                "shortcut_name": shortcut_name or None}

    if sys.platform != "darwin":
        return {"sent": False, "error": "iMessage delivery requires macOS"}

    if not os.path.isfile(pdf_path):
        return {"sent": False, "error": f"file not found: {pdf_path}"}

    # Step 1: optional text body via AppleScript (works reliably).
    text_ok = True
    text_err: str | None = None
    if body:
        text_ok, text_err = _osascript_send_text(to, body)

    # Step 2: file via Shortcuts CLI (the only working attachment path).
    if not shortcut_name:
        return {"sent": text_ok, "to": to,
                "stage": "file",
                "error": ("No shortcut_name configured. AppleScript can't deliver "
                          "attachments on modern macOS — see docs/imessage-setup.md "
                          "for the 90-second Shortcut setup."),
                "text_sent": text_ok}

    file_ok, file_err = _shortcuts_run(shortcut_name, pdf_path)
    if not file_ok:
        return {"sent": False, "stage": "file", "error": file_err,
                "text_sent": text_ok}

    return {"sent": True, "to": to, "pdf_path": pdf_path,
            "text_sent": text_ok, "text_error": text_err}


# ─── AppleScript: plain-text only ───────────────────────────────────────

def _osascript_send_text(recipient: str, message: str) -> tuple[bool, str | None]:
    escaped_msg = (message.replace("\\", "\\\\").replace('"', '\\"')
                          .replace("\n", "\\n"))
    escaped_to = recipient.replace('"', '\\"')
    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{escaped_to}" of targetService
        send "{escaped_msg}" to targetBuddy
    end tell
    '''
    return _run(["osascript", "-e", script], timeout=20)


# ─── Shortcuts CLI: file attachments ────────────────────────────────────

def _shortcuts_run(name: str, file_path: str) -> tuple[bool, str | None]:
    return _run(["shortcuts", "run", name, "-i", file_path], timeout=60)


def _run(argv: list[str], *, timeout: int) -> tuple[bool, str | None]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "").strip()[:300]
        return True, None
    except FileNotFoundError as e:
        return False, str(e)
    except subprocess.TimeoutExpired:
        return False, f"{argv[0]} timed out after {timeout}s"
    except Exception as e:
        return False, str(e)
