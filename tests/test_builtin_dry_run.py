"""The email and notion builtins must never touch a live service on a dry run.

`nia dry-run` is a hard contract: representative mock data, zero network, no live
IMAP, Notion, or Stripe call. These tests lock that contract for the builtins
that reach external services, the same way test_claude_builtin guards the LLM
path and test_presence_glance guards the camera. If a future edit drops a
dry-run guard, one of these turns red.
"""
from __future__ import annotations

from nia.workers._builtins import email, notion


def test_email_sweep_recent_dry_run_returns_mock():
    out = email.sweep_recent(inputs={}, context={"dry_run": True})
    assert out["dry_run"] is True
    assert "unanswered_inbox" in out


def test_notion_due_reminders_dry_run_returns_mock():
    out = notion.due_reminders(inputs={}, context={"dry_run": True})
    assert out["dry_run"] is True


def test_notion_email_sync_dry_run_returns_mock():
    out = notion.email_sync(inputs={}, context={"dry_run": True})
    assert out["dry_run"] is True


def test_notion_git_sync_dry_run_returns_mock():
    out = notion.git_sync(inputs={}, context={"dry_run": True})
    assert out["dry_run"] is True


def test_notion_stripe_sync_dry_run_returns_mock():
    out = notion.stripe_sync(inputs={}, context={"dry_run": True})
    assert out["dry_run"] is True
