"""Tests for the presence-glance worker: a sensor capability under enforced restraint.

This worker is the camera-domain proof of Nia's central thesis. The camera is a
declared, gated capability: the `vision.describe_frame` step is `kind: judgment`
and runs only when its `condition` evaluates true. The four behaviors asserted
here are the whole point:

  1. Load is refused if `camera:read` is not declared (permission enforcement).
  2. Load is refused if the vision step has no `condition` (the gating contract).
  3. When the condition is false, the camera step is SKIPPED and the camera
     builtin is never invoked (runtime gating).
  4. On a dry run, no camera is opened, ever (dry-run safety).

If a future change lets the camera fire without a declared permission, without a
condition, or on a dry run, one of these tests turns red.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nia.runtime import executor
from nia.runtime.manifest import ManifestError, load
from nia.runtime.registry import BUILTIN_WORKERS
from nia.runtime.types import RunStatus
from nia.workers._builtins import sensor, vision


def _write(tmp_path: Path, contents: dict) -> Path:
    p = tmp_path / "worker.yaml"
    p.write_text(yaml.safe_dump(contents))
    return p


def _manifest(*, permissions: list[str], glance_condition: str | None) -> dict:
    glance: dict = {
        "id": "glance",
        "kind": "judgment",
        "impl": "builtin:vision.describe_frame",
        "inputs": {"reason": "confirm a person is at the door"},
    }
    if glance_condition is not None:
        glance["condition"] = glance_condition
    return {
        "name": "presence-glance",
        "version": "0.1.0",
        "schema_version": "0.1",
        "trigger": {"manual": True},
        "permissions": permissions,
        "config": {"source": "front-door", "simulate_motion": False},
        "actions": [
            {
                "id": "check-motion",
                "kind": "deterministic",
                "impl": "builtin:sensor.motion_event",
                "inputs": {
                    "source": "{{ config.source }}",
                    "detected": "{{ config.simulate_motion }}",
                },
            },
            glance,
        ],
    }


# ─── 1. load refused without the camera permission ───────────────────────


def test_load_refused_without_camera_permission(tmp_path):
    """sensor:read alone is not enough; the camera step needs camera:read."""
    path = _write(tmp_path, _manifest(
        permissions=["sensor:read"],
        glance_condition="actions.check-motion.results.detected == true",
    ))
    with pytest.raises(ManifestError, match=r"camera:read"):
        load(path)


def test_load_refused_without_sensor_permission(tmp_path):
    """The motion step needs sensor:read; camera:read alone is not enough."""
    path = _write(tmp_path, _manifest(
        permissions=["camera:read"],
        glance_condition="actions.check-motion.results.detected == true",
    ))
    with pytest.raises(ManifestError, match=r"sensor:read"):
        load(path)


def test_load_accepts_with_both_permissions(tmp_path):
    path = _write(tmp_path, _manifest(
        permissions=["sensor:read", "camera:read"],
        glance_condition="actions.check-motion.results.detected == true",
    ))
    m = load(path)
    assert m.name == "presence-glance"
    assert set(m.permissions) == {"sensor:read", "camera:read"}


# ─── 2. load refused if the camera step has no condition ─────────────────


def test_load_refused_if_vision_step_has_no_condition(tmp_path):
    """A judgment camera step with no condition is an ungated capability. Reject."""
    path = _write(tmp_path, _manifest(
        permissions=["sensor:read", "camera:read"],
        glance_condition=None,
    ))
    with pytest.raises(ManifestError, match=r"condition"):
        load(path)


# ─── 3. camera SKIPPED when the condition is false (and never invoked) ────


def _run(tmp_path, *, simulate_motion: bool, dry_run: bool):
    contents = _manifest(
        permissions=["sensor:read", "camera:read"],
        glance_condition="actions.check-motion.results.detected == true",
    )
    contents["config"]["simulate_motion"] = simulate_motion
    m = load(_write(tmp_path, contents))
    return executor.execute(m, dry_run=dry_run)


def _glance(run):
    return next(a for a in run.actions if a.action_id == "glance")


def test_camera_skipped_when_no_motion(tmp_path, monkeypatch):
    """No motion → the camera builtin must not even be invoked."""
    def explode(*args, **kwargs):
        raise AssertionError("vision.describe_frame must not run when condition is false")
    monkeypatch.setattr(vision, "describe_frame", explode)

    run = _run(tmp_path, simulate_motion=False, dry_run=False)

    glance = _glance(run)
    assert glance.status == RunStatus.SKIPPED
    assert "condition" in (glance.skipped_reason or "")


def test_camera_fires_when_motion_present(tmp_path):
    """Motion present on a real run → the gate opens and the camera step runs."""
    run = _run(tmp_path, simulate_motion=True, dry_run=False)

    glance = _glance(run)
    assert glance.status == RunStatus.SUCCESS
    # No real lens is wired, so nothing is ever actually captured.
    assert glance.results.get("captured") is False


# ─── 4. dry run never opens the camera ───────────────────────────────────


def test_dry_run_never_opens_camera(tmp_path):
    """Even with the condition true, a dry run opens no camera and is labeled."""
    run = _run(tmp_path, simulate_motion=True, dry_run=True)

    glance = _glance(run)
    assert glance.status == RunStatus.SUCCESS
    assert glance.results.get("captured") is False
    assert glance.results.get("dry_run") is True


# ─── builtin unit contracts ──────────────────────────────────────────────


def test_motion_event_reflects_detected_input():
    assert sensor.motion_event(
        inputs={"source": "front-door", "detected": True}, context={},
    )["detected"] is True
    assert sensor.motion_event(
        inputs={"source": "front-door"}, context={},
    )["detected"] is False


def test_vision_dry_run_opens_no_camera():
    out = vision.describe_frame(inputs={"reason": "x"}, context={"dry_run": True})
    assert out["captured"] is False
    assert out["dry_run"] is True


def test_vision_real_run_captures_nothing_without_an_adapter():
    """No camera adapter is wired yet, so a real run captures nothing and says so
    rather than pretending. The containment point stands: this path is only
    reachable under a granted permission and a true condition."""
    out = vision.describe_frame(inputs={"reason": "x"}, context={"dry_run": False})
    assert out["captured"] is False


# ─── the bundled worker must load ────────────────────────────────────────


def test_bundled_presence_glance_loads():
    path = BUILTIN_WORKERS / "presence-glance" / "worker.yaml"
    assert path.is_file(), "presence-glance must ship as a bundled reference worker"
    m = load(path)
    assert m.name == "presence-glance"
    assert set(m.permissions) == {"sensor:read", "camera:read"}
