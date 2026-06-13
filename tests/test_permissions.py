"""Tests for soft permission enforcement at manifest load time."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nia.runtime import permissions as perms
from nia.runtime.manifest import ManifestError, load


# ─── covers() and missing_permissions() ─────────────────────────────────


def test_covers_equality():
    assert perms.covers("imap:read", "imap:read")


def test_covers_more_specific_grant():
    """A grant with extra :resource covers the broader requirement."""
    assert perms.covers("filesystem:write:~/.nia/briefs", "filesystem:write")


def test_does_not_cover_more_general_grant():
    """A grant that's vaguer than the requirement does NOT cover it."""
    assert not perms.covers("imap", "imap:read")


def test_does_not_cover_different_service():
    assert not perms.covers("notion:read", "imap:read")


def test_missing_permissions_unknown_impl_is_empty():
    """We cannot statically analyze file: impls; assume nothing required."""
    assert perms.missing_permissions("file:./worker.py:run", ["a", "b"]) == set()


def test_missing_permissions_for_known_builtin():
    missing = perms.missing_permissions("builtin:email.sweep_recent", [])
    assert missing == {"imap:read"}


def test_missing_permissions_satisfied_by_exact_grant():
    missing = perms.missing_permissions("builtin:email.sweep_recent", ["imap:read"])
    assert missing == set()


def test_missing_permissions_satisfied_by_more_specific_grant():
    missing = perms.missing_permissions(
        "builtin:render.morning_brief_pdf",
        ["filesystem:write:~/.nia/briefs"],
    )
    assert missing == set()


def test_missing_permissions_partial_grant():
    missing = perms.missing_permissions(
        "builtin:notion.email_sync",
        ["notion:write"],  # missing imap:read
    )
    assert missing == {"imap:read"}


def test_missing_permissions_unknown_builtin_assumed_empty():
    """A builtin not registered in BUILTIN_REQUIREMENTS needs nothing."""
    missing = perms.missing_permissions("builtin:debug.echo", [])
    assert missing == set()


# ─── manifest loader integration ────────────────────────────────────────


def _write_manifest(tmp_path: Path, contents: dict) -> Path:
    p = tmp_path / "worker.yaml"
    p.write_text(yaml.safe_dump(contents))
    return p


def test_loader_rejects_worker_missing_required_permission(tmp_path):
    manifest = _write_manifest(tmp_path, {
        "name": "bad-worker",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        # NO permissions: block. Action requires imap:read.
        "actions": [{
            "id": "sweep",
            "kind": "deterministic",
            "impl": "builtin:email.sweep_recent",
        }],
    })
    with pytest.raises(ManifestError, match=r"requires permissions.*'imap:read'"):
        load(manifest)


def test_loader_accepts_worker_with_correct_permissions(tmp_path):
    manifest = _write_manifest(tmp_path, {
        "name": "good-worker",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        "permissions": ["imap:read"],
        "actions": [{
            "id": "sweep",
            "kind": "deterministic",
            "impl": "builtin:email.sweep_recent",
        }],
    })
    m = load(manifest)
    assert m.name == "good-worker"


def test_loader_rejects_partial_permissions(tmp_path):
    """email.sweep_recent + claude.classify needs both perms; only one declared."""
    manifest = _write_manifest(tmp_path, {
        "name": "partial-perms",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        "permissions": ["imap:read"],  # missing llm:claude
        "actions": [
            {"id": "sweep", "kind": "deterministic",
             "impl": "builtin:email.sweep_recent"},
            {"id": "classify", "kind": "judgment",
             "condition": "true",
             "impl": "builtin:claude.classify"},
        ],
    })
    with pytest.raises(ManifestError, match=r"llm:claude"):
        load(manifest)


def test_loader_accepts_more_specific_grant(tmp_path):
    """filesystem:write:~/.nia/briefs covers filesystem:write."""
    manifest = _write_manifest(tmp_path, {
        "name": "specific-grant",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        "permissions": ["filesystem:write:~/.nia/briefs"],
        "actions": [{
            "id": "render",
            "kind": "deterministic",
            "impl": "builtin:render.morning_brief_pdf",
        }],
    })
    m = load(manifest)
    assert m.permissions == ["filesystem:write:~/.nia/briefs"]


def test_loader_accepts_worker_with_no_permission_requirements(tmp_path):
    """debug.echo needs no permissions, so a worker without any can load."""
    manifest = _write_manifest(tmp_path, {
        "name": "no-perms-needed",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        "actions": [{
            "id": "greet",
            "kind": "deterministic",
            "impl": "builtin:debug.echo",
            "inputs": {"message": "hi"},
        }],
    })
    m = load(manifest)
    assert m.permissions == []


# ─── all bundled workers must pass ──────────────────────────────────────


@pytest.mark.parametrize("worker_name", [
    "hello-world", "morning-ops", "notion-sync", "inbox-triage",
])
def test_bundled_workers_pass_permission_check(worker_name):
    """The bundled workers MUST load. If a new builtin is added, the
    BUILTIN_REQUIREMENTS mapping and the bundled worker's permissions
    block must be updated together.
    """
    from nia.runtime.registry import BUILTIN_WORKERS
    path = BUILTIN_WORKERS / worker_name / "worker.yaml"
    if not path.is_file():
        pytest.skip(f"{worker_name} not bundled")
    m = load(path)
    assert m.name == worker_name
