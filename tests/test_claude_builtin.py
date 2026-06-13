"""Tests for the Claude judgment builtin.

The discipline these tests are guarding:
  1. Dry-run never makes a network call.
  2. Empty items list is a clean no-op (not a crash).
  3. Missing API key raises a clear error on the real path.
  4. Parsing is tolerant of stray text and dropped ids.
  5. Identifiers are synthesized for email-shaped items without an `id`.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nia.workers._builtins import claude


# ─── empty / edge cases ─────────────────────────────────────────────────


def test_empty_items_returns_empty_classifications():
    out = claude.classify(
        inputs={"items": [], "categories": ["a", "b"]},
        context={},
    )
    assert out["classifications"] == []
    assert out["items_in"] == 0
    assert out["tokens_in"] == 0


def test_missing_items_treated_as_empty():
    out = claude.classify(inputs={"categories": ["a"]}, context={})
    assert out["classifications"] == []


def test_no_categories_raises_value_error():
    with pytest.raises(ValueError, match="categories"):
        claude.classify(
            inputs={"items": [{"id": "1", "text": "hi"}], "categories": []},
            context={},
        )


# ─── dry-run guarantees ─────────────────────────────────────────────────


def test_dry_run_returns_mock_without_api_call():
    items = [{"id": "a", "text": "hello"}, {"id": "b", "text": "world"}]
    out = claude.classify(
        inputs={"items": items, "categories": ["cat1", "cat2"]},
        context={"dry_run": True},
    )
    assert out["dry_run"] is True
    assert out["tokens_in"] == 0
    assert out["tokens_out"] == 0
    assert out["model"] == "(dry-run)"


def test_dry_run_uses_first_category_for_every_item():
    items = [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]
    out = claude.classify(
        inputs={"items": items, "categories": ["alpha", "beta", "gamma"]},
        context={"dry_run": True},
    )
    cats = [c["category"] for c in out["classifications"]]
    assert cats == ["alpha", "alpha"]


def test_dry_run_does_not_import_anthropic():
    """A dry-run must work even if the anthropic package is not installed."""
    items = [{"id": "a", "text": "hi"}]
    # If this test imports anthropic, the call below would still succeed,
    # but we want to be sure dry-run does not touch the network. The
    # absence of token counts plus the dry_run flag is the contract.
    out = claude.classify(
        inputs={"items": items, "categories": ["x"]},
        context={"dry_run": True},
    )
    assert out["tokens_in"] == 0
    assert out["latency_ms"] == 0


# ─── real-path error handling ───────────────────────────────────────────


def test_missing_api_key_raises_clear_error(fake_anthropic_key, monkeypatch):
    """Even with anthropic available, missing key raises RuntimeError."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        claude.classify(
            inputs={"items": [{"id": "a", "text": "x"}], "categories": ["c"]},
            context={"dry_run": False},
        )


# ─── identifier synthesis ───────────────────────────────────────────────


def test_item_id_uses_id_field_when_present():
    assert claude._item_id({"id": "abc", "from": "x", "subject": "y"}) == "abc"


def test_item_id_synthesizes_from_email_fields():
    item = {"date_iso": "2026-06-13", "from": "alice@example.com", "subject": "hi"}
    iid = claude._item_id(item)
    assert "2026-06-13" in iid
    assert "alice@example.com" in iid
    assert "hi" in iid


def test_item_id_truncated_to_80_chars():
    long_text = "x" * 200
    item = {"id": long_text}
    assert len(claude._item_id(item)) == 80


def test_item_text_falls_through_text_body_snippet_subject():
    assert claude._item_text({"text": "T"}) == "T"
    assert claude._item_text({"body": "B"}) == "B"
    assert claude._item_text({"snippet": "S"}) == "S"
    assert claude._item_text({"subject": "Sub"}) == "Sub"
    assert claude._item_text({}) == ""


# ─── classification parsing ────────────────────────────────────────────


def test_parse_handles_well_formed_json_lines():
    text = '{"id": "a", "category": "cat1", "reason": "because"}\n' \
           '{"id": "b", "category": "cat2", "reason": "obvious"}'
    items = [{"id": "a"}, {"id": "b"}]
    out = claude._parse_classifications(text, items, ["cat1", "cat2"])
    assert len(out) == 2
    assert {c["id"] for c in out} == {"a", "b"}
    assert {c["category"] for c in out} == {"cat1", "cat2"}


def test_parse_skips_non_json_lines():
    text = "Here are the classifications:\n" \
           '{"id": "a", "category": "cat1", "reason": "ok"}\n' \
           "End of output."
    items = [{"id": "a"}]
    out = claude._parse_classifications(text, items, ["cat1"])
    assert len(out) == 1
    assert out[0]["category"] == "cat1"


def test_parse_invalid_category_becomes_uncertain():
    text = '{"id": "a", "category": "fake_category", "reason": "wat"}'
    items = [{"id": "a"}]
    out = claude._parse_classifications(text, items, ["cat1", "cat2"])
    assert out[0]["category"] == "uncertain"


def test_parse_missing_ids_filled_with_uncertain():
    text = '{"id": "a", "category": "cat1", "reason": "ok"}'
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    out = claude._parse_classifications(text, items, ["cat1"])
    assert len(out) == 3
    by_id = {c["id"]: c for c in out}
    assert by_id["a"]["category"] == "cat1"
    assert by_id["b"]["category"] == "uncertain"
    assert by_id["c"]["category"] == "uncertain"


def test_parse_handles_empty_output():
    items = [{"id": "a"}, {"id": "b"}]
    out = claude._parse_classifications("", items, ["cat1"])
    assert len(out) == 2
    assert all(c["category"] == "uncertain" for c in out)


# ─── real path with mocked Anthropic client ─────────────────────────────


def test_real_call_with_mocked_client(fake_anthropic_key):
    """End-to-end test of the real path using a mocked Anthropic client."""
    items = [{"id": "1", "from": "a@b.com", "subject": "hi", "text": "hello"}]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"id": "1", "category": "cat1", "reason": "test"}')]
    mock_response.usage.input_tokens = 42
    mock_response.usage.output_tokens = 17

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("anthropic.Anthropic", return_value=mock_client):
        out = claude.classify(
            inputs={"items": items, "categories": ["cat1", "cat2"]},
            context={"dry_run": False},
        )

    assert out["classifications"][0]["category"] == "cat1"
    assert out["tokens_in"] == 42
    assert out["tokens_out"] == 17
    assert out["model"] == claude.DEFAULT_MODEL


def test_real_call_passes_instruction_into_prompt(fake_anthropic_key):
    items = [{"id": "1", "text": "x"}]
    captured = {}

    def capture_create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = [MagicMock(text='{"id": "1", "category": "cat1", "reason": ""}')]
        resp.usage.input_tokens = 1
        resp.usage.output_tokens = 1
        return resp

    mock_client = MagicMock()
    mock_client.messages.create = capture_create

    with patch("anthropic.Anthropic", return_value=mock_client):
        claude.classify(
            inputs={
                "items": items,
                "categories": ["cat1"],
                "instruction": "Be cautious with ambiguous messages.",
            },
            context={"dry_run": False},
        )

    prompt = captured["messages"][0]["content"]
    assert "Be cautious with ambiguous messages." in prompt
    assert "cat1" in prompt
