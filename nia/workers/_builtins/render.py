"""Render builtins — produce artifacts (PDFs, files) from worker results."""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path


def morning_brief_pdf(*, inputs: dict, context: dict) -> dict:
    """Render the daily morning brief as a one-page PDF.

    Inputs:
      email:    dict from email.sweep_recent
      notion:   dict from notion.due_reminders
      output_dir: filesystem path (default ~/.nia/briefs)
      shift_note: optional string at top (e.g., "Walmart 5 AM – 3:30 PM")
      headline: optional string (e.g., "TUESDAY — BUILD DAY")

    Returns:
      {"pdf_path": "..."}

    Requires the optional `fpdf2` package. If not installed, falls back to
    writing a plain .txt brief — caller still gets a path it can deliver.
    """
    email = inputs.get("email") or {}
    notion = inputs.get("notion") or {}
    out_dir = Path(os.path.expanduser(inputs.get("output_dir", "~/.nia/briefs")))
    out_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    headline = inputs.get("headline") or _default_headline(today)
    shift_note = inputs.get("shift_note", "")
    # Filename doubles as the iMessage preview text — make it descriptive.
    # Example: Wednesday_May_13_BUILD_DAY.pdf
    day_theme = ["SALES", "BUILD", "CONTENT", "REVIEW", "WALMART",
                 "WALMART", "WALMART"][today.weekday()]
    fname = f"{today.strftime('%A_%b_%d')}_{day_theme}_DAY"

    if context.get("dry_run"):
        return {"pdf_path": str(out_dir / f"{fname}.pdf"),
                "would_write": True, "format": "pdf"}

    # Try PDF first, fall back to txt if fpdf2 not available.
    try:
        path = _render_pdf(out_dir / f"{fname}.pdf", today, headline,
                           shift_note, email, notion)
        return {"pdf_path": str(path), "format": "pdf"}
    except ImportError:
        path = _render_txt(out_dir / f"{fname}.txt", today, headline,
                           shift_note, email, notion)
        return {"pdf_path": str(path), "format": "txt"}


def _default_headline(today: date) -> str:
    days = ["MONDAY - SALES", "TUESDAY - BUILD", "WEDNESDAY - CONTENT",
            "THURSDAY - REVIEW", "FRIDAY - WALMART", "SATURDAY - WALMART",
            "SUNDAY - WALMART"]
    return f"{today.strftime('%A, %B %d, %Y').upper()} - {days[today.weekday()]}"


# fpdf2's bundled Helvetica is latin-1 only. Strip / replace non-ASCII so a
# user-supplied subject line with smart quotes or em-dashes doesn't crash
# the worker. v0.2 will ship a real Unicode font.
_UNICODE_MAP = str.maketrans({
    "—": "-", "–": "-",   # em-dash, en-dash
    "‘": "'", "’": "'",   # smart quotes
    "“": '"', "”": '"',
    "•": "-", "·": "-",   # bullet, middle dot
    "→": ">", "←": "<",   # arrows
    "…": "...",                # ellipsis
})


def _safe(s) -> str:
    if not isinstance(s, str):
        s = str(s)
    return s.translate(_UNICODE_MAP).encode("latin-1", "replace").decode("latin-1")


def _render_pdf(path: Path, today: date, headline: str, shift_note: str,
                email: dict, notion: dict) -> Path:
    from fpdf import FPDF  # noqa: import-outside-toplevel — optional dep

    pdf = FPDF(format="letter")
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    # Header
    pdf.set_fill_color(15, 15, 15)
    pdf.rect(0, 0, 220, 32, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(12, 8)
    pdf.cell(0, 4, _safe(today.strftime("%A, %B %d, %Y").upper()))
    pdf.set_xy(12, 14)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 8, _safe(headline))
    if shift_note:
        pdf.set_xy(12, 24)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(230, 57, 70)
        pdf.cell(0, 4, _safe(shift_note))

    pdf.set_xy(12, 42)
    pdf.set_text_color(0, 0, 0)

    # Top reminders
    _section(pdf, "TODAY'S TOP " + str(len(notion.get("reminders", []))))
    if not notion.get("reminders"):
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "  (no open reminders)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    for i, r in enumerate(notion.get("reminders", []), 1):
        pdf.set_font("Helvetica", "B", 10)
        title = f"  {i}. {r.get('title','')[:80]}"
        pdf.cell(0, 6, _safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        meta = f"      {r.get('priority','-')} - due {r.get('due','-')} - {r.get('business','-')}"
        pdf.cell(0, 5, _safe(meta), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.ln(4)
    # Unanswered inbox
    unanswered = email.get("unanswered_inbox", [])
    _section(pdf, f"INBOX: UNANSWERED ({email.get('unanswered_count', len(unanswered))})")
    if not unanswered:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "  (inbox zero across all accounts)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    for i in unanswered[:8]:
        pdf.set_font("Helvetica", "", 9)
        line = f"  ! {i.get('from_name','')[:38]:<38}  {i.get('subject','')[:50]}"
        pdf.cell(0, 5, _safe(line), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    # Recently sent
    sent = email.get("recently_sent", [])
    _section(pdf, f"RECENTLY SENT (last 48h, {email.get('recently_sent_count', len(sent))})")
    if not sent:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "  (no outbound in last 48h)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    for s in sent[-8:]:
        pdf.set_font("Helvetica", "", 9)
        line = f"  > {s.get('to','')[:38]:<38}  {s.get('subject','')[:50]}"
        pdf.cell(0, 5, _safe(line), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    # The one question
    pdf.set_fill_color(230, 57, 70)
    pdf.rect(10, pdf.get_y(), 195, 22, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(14, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 4, "THE ONE QUESTION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(14, pdf.get_y() + 1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5, _safe('"What is the ONE thing I can do today that makes tomorrow easier?"'))

    pdf.output(str(path))
    return path


def _section(pdf, title: str) -> None:
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 7, "  " + title, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _render_txt(path: Path, today: date, headline: str, shift_note: str,
                email: dict, notion: dict) -> Path:
    lines = []
    lines.append("=" * 70)
    lines.append(headline)
    lines.append(today.strftime("%A, %B %d, %Y"))
    if shift_note:
        lines.append(shift_note)
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"TOP REMINDERS ({notion.get('total_open', 0)} open)")
    lines.append("-" * 70)
    for i, r in enumerate(notion.get("reminders", []), 1):
        lines.append(f"  {i}. [{r.get('priority','-')}] {r.get('title','')[:80]}")
        lines.append(f"     due {r.get('due','-')} · {r.get('business','-')}")
    lines.append("")
    lines.append(f"UNANSWERED INBOX ({email.get('unanswered_count', 0)})")
    lines.append("-" * 70)
    for i in email.get("unanswered_inbox", [])[:10]:
        lines.append(f"  ! {i.get('from_name','')[:40]:<40}  {i.get('subject','')[:50]}")
    lines.append("")
    lines.append(f"RECENTLY SENT ({email.get('recently_sent_count', 0)})")
    lines.append("-" * 70)
    for s in email.get("recently_sent", [])[-10:]:
        lines.append(f"  > {s.get('to','')[:40]:<40}  {s.get('subject','')[:50]}")
    lines.append("")
    lines.append('THE ONE QUESTION')
    lines.append('"What is the ONE thing I can do today that makes tomorrow easier?"')

    path.write_text("\n".join(lines))
    return path
