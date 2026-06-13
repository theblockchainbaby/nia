"""Tests for v0.2 nia worker install + enable.

These tests are hermetic:
  - HOME is redirected to tmp_path by conftest.isolate_environment, so
    install writes to a temp ~/.nia and enable writes to a temp
    ~/Library/LaunchAgents.
  - subprocess.run is monkeypatched so launchctl never actually runs.
  - platform.system is monkeypatched in non-macOS tests.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nia.cli.commands import worker as wcmd


# ─── _label_safe ────────────────────────────────────────────────────────


def test_label_safe_lowercases_and_strips_punctuation():
    assert wcmd._label_safe("Hello-World") == "helloworld"
    assert wcmd._label_safe("inbox-triage") == "inboxtriage"
    assert wcmd._label_safe("my_worker.v1") == "myworkerv1"


# ─── _schedule_xml ──────────────────────────────────────────────────────


def test_schedule_xml_for_interval_seconds():
    out = wcmd._schedule_xml(None, 300)
    assert "<key>StartInterval</key>" in out
    assert "<integer>300</integer>" in out


def test_schedule_xml_for_simple_cron_daily_3am():
    out = wcmd._schedule_xml("0 3 * * *", None)
    assert "<key>StartCalendarInterval</key>" in out
    assert "<key>Hour</key>" in out
    assert "<integer>3</integer>" in out
    assert "<key>Minute</key>" in out
    assert "<integer>0</integer>" in out


def test_schedule_xml_for_hourly_top_of_hour():
    out = wcmd._schedule_xml("0 * * * *", None)
    assert "<key>Minute</key>" in out
    assert "<integer>0</integer>" in out
    # Hour wildcard means no Hour key.
    assert "<key>Hour</key>" not in out


def test_schedule_xml_for_comma_cron_yields_array():
    out = wcmd._schedule_xml("0 6,18 * * *", None)
    assert "<array>" in out
    assert out.count("<dict>") >= 2


def test_schedule_xml_rejects_step_syntax():
    with pytest.raises(ValueError, match="not yet supported"):
        wcmd._schedule_xml("*/15 * * * *", None)


def test_schedule_xml_rejects_range_syntax():
    with pytest.raises(ValueError, match="not yet supported"):
        wcmd._schedule_xml("0 9-17 * * *", None)


def test_schedule_xml_rejects_malformed_cron():
    with pytest.raises(ValueError, match="5 fields"):
        wcmd._schedule_xml("0 3 *", None)


# ─── worker_install ─────────────────────────────────────────────────────


def test_install_unknown_worker_returns_error(capsys):
    rc = wcmd.worker_install("totally-not-a-real-worker")
    assert rc == 1


def test_install_copies_hello_world_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(wcmd, "USER_WORKERS", tmp_path / "workers")
    rc = wcmd.worker_install("hello-world")
    assert rc == 0
    user_manifest = tmp_path / "workers" / "hello-world" / "worker.yaml"
    assert user_manifest.is_file()
    text = user_manifest.read_text()
    assert "name: hello-world" in text


def test_install_scaffolds_config_template(tmp_path, monkeypatch):
    monkeypatch.setattr(wcmd, "USER_WORKERS", tmp_path / "workers")
    wcmd.worker_install("hello-world")
    config_template = tmp_path / "workers" / "hello-world" / "config.yaml.template"
    assert config_template.is_file()
    assert "hello-world" in config_template.read_text()


def test_install_scaffolds_accounts_template_for_email_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(wcmd, "USER_WORKERS", tmp_path / "workers")
    rc = wcmd.worker_install("morning-ops")
    assert rc == 0
    accounts_template = tmp_path / "workers" / "morning-ops" / "accounts.yaml.template"
    assert accounts_template.is_file()
    text = accounts_template.read_text()
    assert "accounts:" in text
    assert "imap.gmail.com" in text


def test_install_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(wcmd, "USER_WORKERS", tmp_path / "workers")
    # First install.
    wcmd.worker_install("hello-world")
    user_manifest = tmp_path / "workers" / "hello-world" / "worker.yaml"
    # User customizes.
    custom = "name: hello-world\n# user customized this\n"
    user_manifest.write_text(custom)
    # Second install must not clobber.
    wcmd.worker_install("hello-world")
    assert user_manifest.read_text() == custom


# ─── worker_enable ──────────────────────────────────────────────────────


@pytest.fixture
def fake_macos(monkeypatch):
    """Pretend we are on macOS regardless of host."""
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    # Stub launchctl so we never actually load anything.
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: completed)


def test_enable_refuses_non_macos(monkeypatch, capsys):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    rc = wcmd.worker_enable("hello-world")
    assert rc == 1


def test_enable_refuses_manual_worker(fake_macos, tmp_path, monkeypatch):
    """hello-world has trigger: manual; cannot be scheduled."""
    monkeypatch.setattr(wcmd, "LAUNCH_AGENTS", tmp_path / "LaunchAgents")
    rc = wcmd.worker_enable("hello-world")
    assert rc == 1


def test_enable_refuses_unknown_worker(fake_macos, tmp_path, monkeypatch):
    monkeypatch.setattr(wcmd, "LAUNCH_AGENTS", tmp_path / "LaunchAgents")
    rc = wcmd.worker_enable("totally-not-a-real-worker")
    assert rc == 1


def test_enable_writes_valid_plist_for_cron_worker(
    fake_macos, tmp_path, monkeypatch
):
    """inbox-triage has cron 0 * * * * and should produce a valid plist."""
    monkeypatch.setattr(wcmd, "LAUNCH_AGENTS", tmp_path / "LaunchAgents")
    rc = wcmd.worker_enable("inbox-triage")
    assert rc == 0
    plist_path = tmp_path / "LaunchAgents" / "com.nia.inboxtriage.plist"
    assert plist_path.is_file()
    plist = plist_path.read_text()
    assert "<key>Label</key>" in plist
    assert "<string>com.nia.inboxtriage</string>" in plist
    assert "nia worker run inbox-triage" in plist
    assert "<key>StartCalendarInterval</key>" in plist
    assert "<key>Minute</key>" in plist
    assert "<integer>0</integer>" in plist


def test_enable_includes_env_source_when_env_file_exists(
    fake_macos, tmp_path, monkeypatch
):
    monkeypatch.setattr(wcmd, "LAUNCH_AGENTS", tmp_path / "LaunchAgents")
    # Create the env file at the default location.
    env_file = tmp_path / ".nia" / "env"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("FOO=bar\n")
    monkeypatch.setattr(wcmd, "DEFAULT_ENV_FILE", env_file)
    wcmd.worker_enable("inbox-triage")
    plist = (tmp_path / "LaunchAgents" / "com.nia.inboxtriage.plist").read_text()
    assert f"source {env_file}" in plist


def test_enable_omits_env_source_when_env_file_absent(
    fake_macos, tmp_path, monkeypatch
):
    monkeypatch.setattr(wcmd, "LAUNCH_AGENTS", tmp_path / "LaunchAgents")
    monkeypatch.setattr(wcmd, "DEFAULT_ENV_FILE", Path("/nonexistent/path"))
    wcmd.worker_enable("inbox-triage")
    plist = (tmp_path / "LaunchAgents" / "com.nia.inboxtriage.plist").read_text()
    assert "source " not in plist
