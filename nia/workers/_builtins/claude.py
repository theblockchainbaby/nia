"""Claude (Anthropic) builtins — the mediated judgment surface.

Workers invoke Claude via these builtins as `kind: judgment` actions. The
runtime gates every call behind a manifest-declared `condition:`, so the
model is invoked only when the worker's prior deterministic steps have
produced state that the condition evaluates true against. This is the
structural distinction Nia stakes: judgment is a declared exception, not
the default execution mode.

On a dry-run (`nia dry-run worker <name>`), builtins return representative
mock output and never call the Anthropic API. The contract is hard: no
tokens are spent on a dry-run, ever.
"""
from __future__ import annotations

import json
import os
import time

# Default model: Haiku 4.5 is fast and cheap for classification.
# Workers can override via the `model` input.
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 512


def classify(*, inputs: dict, context: dict) -> dict:
    """Classify a batch of items into a fixed list of categories.

    Inputs:
      items: list of dicts. Each item is classified independently. The
        builtin extracts an identifier and a text payload from each item
        flexibly (see `_item_id` / `_item_text` below) so the worker does
        not have to rename fields.
      categories: list of category strings, e.g.
        ["customer", "vendor", "recruiter", "personal", "spam", "other"]
      instruction: optional, a short context note prepended to the prompt.
      model: optional, defaults to claude-haiku-4-5.
      max_tokens: optional, defaults to 512.

    Returns:
      {
        "classifications": list of {id, category, reason},
        "model": str,
        "items_in": int,
        "items_out": int,
        "tokens_in": int,
        "tokens_out": int,
        "latency_ms": int,
      }

    Errors raised:
      ValueError if `categories` is empty.
      RuntimeError if `anthropic` package is missing or ANTHROPIC_API_KEY
      is unset (only on real runs; dry-run never raises these).
    """
    items = list(inputs.get("items") or [])
    categories = list(inputs.get("categories") or [])

    # Empty items is a normal no-op (the worker condition probably evaluated
    # true when items count > 0 but a race or template error landed here).
    if not items:
        return _empty_result()

    if not categories:
        raise ValueError("claude.classify requires non-empty `categories`")

    if context.get("dry_run"):
        return _dry_run_result(items, categories)

    instruction = (inputs.get("instruction") or "").strip()
    model = str(inputs.get("model") or DEFAULT_MODEL)
    max_tokens = int(inputs.get("max_tokens") or DEFAULT_MAX_TOKENS)

    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic package not installed. Install with: "
            "pip install -e '.[judgment]'"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    client = Anthropic(api_key=api_key)
    prompt = _build_classify_prompt(items, categories, instruction)

    started = time.monotonic()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    text = response.content[0].text if response.content else ""
    classifications = _parse_classifications(text, items, categories)

    return {
        "classifications": classifications,
        "model": model,
        "items_in": len(items),
        "items_out": len(classifications),
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
        "latency_ms": latency_ms,
    }


# ─── helpers ────────────────────────────────────────────────────────────


def _item_id(it: dict) -> str:
    """Extract an item identifier, flexibly.

    Tries `id` first, then synthesizes from date + sender + subject (so
    email-shaped items work without the worker renaming fields).
    """
    if "id" in it and it["id"] is not None:
        return str(it["id"])[:80]
    parts = []
    for k in ("date_iso", "from", "subject"):
        v = it.get(k)
        if v:
            parts.append(str(v))
    if parts:
        return "|".join(parts)[:80]
    return f"item_{id(it)}"


def _item_text(it: dict) -> str:
    """Extract item text content, flexibly.

    Tries `text`, then `body`, then `snippet`, then falls back to subject.
    """
    for k in ("text", "body", "snippet"):
        v = it.get(k)
        if v:
            return str(v)
    return str(it.get("subject", ""))


def _build_classify_prompt(items: list, categories: list, instruction: str) -> str:
    cats = ", ".join(categories)
    intro = (instruction + "\n\n") if instruction else ""
    body_lines: list[str] = []
    for it in items:
        item_id = _item_id(it)
        from_ = it.get("from") or ""
        subj = it.get("subject") or ""
        text = _item_text(it)
        header = f"ID: {item_id}"
        if from_:
            header += f"\nFROM: {from_}"
        if subj:
            header += f"\nSUBJECT: {subj}"
        if text and text != subj:
            header += f"\nBODY: {text[:500]}"
        body_lines.append(header)
        body_lines.append("---")
    body = "\n".join(body_lines)
    return (
        f"{intro}"
        f"Classify each item below into exactly one of these categories: {cats}.\n"
        f'If you are uncertain, use the category "uncertain".\n'
        f"For each item, output one JSON object on its own line with keys:\n"
        f'  id, category, reason\n'
        f"Output ONLY JSON lines (one per item), no commentary, no markdown.\n\n"
        f"{body}\n\n"
        f"Output:"
    )


def _parse_classifications(text: str, items: list, categories: list) -> list[dict]:
    """Parse the model's JSON-lines output. Tolerant of stray text.

    For every input item, output exactly one classification (filling in
    `category=uncertain, reason="model did not return this id"` if the
    model dropped the id). This keeps the worker contract stable.
    """
    valid_cats = set(categories) | {"uncertain"}
    id_to_item = {_item_id(it): it for it in items}
    parsed: dict[str, dict] = {}
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        item_id = str(obj.get("id", "")).strip()[:80]
        if not item_id:
            continue
        category = str(obj.get("category", "uncertain")).strip()
        if category not in valid_cats:
            category = "uncertain"
        reason = str(obj.get("reason", "")).strip()[:200]
        parsed[item_id] = {"id": item_id, "category": category, "reason": reason}

    # Ensure one row per input item.
    out: list[dict] = []
    for iid in id_to_item:
        if iid in parsed:
            out.append(parsed[iid])
        else:
            out.append({
                "id": iid,
                "category": "uncertain",
                "reason": "model output did not include this id",
            })
    return out


def _empty_result() -> dict:
    return {
        "classifications": [],
        "model": "(none)",
        "items_in": 0,
        "items_out": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
    }


def _dry_run_result(items: list, categories: list) -> dict:
    """Mock classification: every item gets the first category."""
    return {
        "classifications": [
            {
                "id": _item_id(it),
                "category": categories[0],
                "reason": "(dry-run mock; LLM not called)",
            }
            for it in items
        ],
        "model": "(dry-run)",
        "items_in": len(items),
        "items_out": len(items),
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
        "dry_run": True,
    }
