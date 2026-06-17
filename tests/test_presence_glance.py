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
from nia.adapters import camera, presence


# A stand-in for a real capture so tests stay deterministic and never touch
# actual hardware (CI has no camera).
_FAKE_FRAME = {
    "captured": True, "path": "/tmp/frame_test.jpg", "device": "0",
    "captured_at": "2026-01-01T00:00:00+00:00", "bytes": 4096,
}


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
    """No presence → the camera builtin must not even be invoked."""
    def explode(*args, **kwargs):
        raise AssertionError("vision.describe_frame must not run when condition is false")
    monkeypatch.setattr(vision, "describe_frame", explode)
    monkeypatch.setattr(presence, "read_presence", lambda **k: {
        "detected": False, "idle_seconds": 60.0, "window_seconds": 5.0,
        "signal": "hid", "read_at": None})

    run = _run(tmp_path, simulate_motion=False, dry_run=False)

    glance = _glance(run)
    assert glance.status == RunStatus.SKIPPED
    assert "condition" in (glance.skipped_reason or "")


def test_camera_fires_and_captures_when_motion_present(tmp_path, monkeypatch):
    """Presence on a real run → the gate opens and the camera captures."""
    monkeypatch.setattr(presence, "read_presence", lambda **k: {
        "detected": True, "idle_seconds": 1.0, "window_seconds": 5.0,
        "signal": "hid", "read_at": None})
    monkeypatch.setattr(camera, "capture_frame", lambda **k: dict(_FAKE_FRAME))

    run = _run(tmp_path, simulate_motion=True, dry_run=False)

    glance = _glance(run)
    assert glance.status == RunStatus.SUCCESS
    assert glance.results.get("captured") is True
    assert glance.results.get("path", "").endswith(".jpg")


# ─── 4. dry run never opens the camera ───────────────────────────────────


def test_dry_run_never_opens_camera(tmp_path, monkeypatch):
    """Even with the condition true, a dry run opens no camera and reads no
    hardware sensor; both come from simulation, and the run is labeled."""
    def explode(**k):
        raise AssertionError("dry run must not open the camera")
    monkeypatch.setattr(camera, "capture_frame", explode)
    def no_hw(**k):
        raise AssertionError("dry run must not read the presence sensor")
    monkeypatch.setattr(presence, "read_presence", no_hw)

    run = _run(tmp_path, simulate_motion=True, dry_run=True)

    glance = _glance(run)
    assert glance.status == RunStatus.SUCCESS
    assert glance.results.get("captured") is False
    assert glance.results.get("dry_run") is True


# ─── builtin unit contracts ──────────────────────────────────────────────


def test_motion_event_dry_run_reflects_config():
    """In dry run the signal is simulated from config and touches no hardware."""
    assert sensor.motion_event(
        inputs={"source": "front-door", "detected": True},
        context={"dry_run": True},
    )["detected"] is True
    assert sensor.motion_event(
        inputs={"source": "front-door"},
        context={"dry_run": True},
    )["detected"] is False


def test_motion_event_real_run_reads_presence(monkeypatch):
    """A real run reads the presence adapter and records the idle decision."""
    monkeypatch.setattr(presence, "read_presence", lambda **k: {
        "detected": True, "idle_seconds": 1.2, "window_seconds": 5.0,
        "signal": "hid", "read_at": None})
    out = sensor.motion_event(inputs={"source": "desk"}, context={})
    assert out["detected"] is True
    assert out["signal"] == "hid"
    assert out["idle_seconds"] == 1.2
    assert "<=" in out["reason"]


def test_motion_event_degrades_when_presence_unavailable(monkeypatch):
    """If the adapter cannot read, the builtin degrades to detected=false."""
    def boom(**k):
        raise presence.PresenceError("ioreg not found")
    monkeypatch.setattr(presence, "read_presence", boom)
    out = sensor.motion_event(inputs={"source": "desk"}, context={})
    assert out["detected"] is False
    assert "unavailable" in out["reason"]


def test_vision_dry_run_opens_no_camera(monkeypatch):
    def explode(**k):
        raise AssertionError("dry run must not open the camera")
    monkeypatch.setattr(camera, "capture_frame", explode)
    out = vision.describe_frame(inputs={"reason": "x"}, context={"dry_run": True})
    assert out["captured"] is False
    assert out["dry_run"] is True


def test_vision_real_run_captures_a_frame(monkeypatch):
    """A real run delegates to the adapter and reports the captured frame."""
    monkeypatch.setattr(camera, "capture_frame", lambda **k: dict(_FAKE_FRAME))
    out = vision.describe_frame(inputs={"reason": "door"}, context={"dry_run": False})
    assert out["captured"] is True
    assert out["path"].endswith(".jpg")
    assert out["reason"] == "door"


def test_vision_real_run_graceful_when_camera_unavailable(monkeypatch):
    """If the adapter cannot capture, the builtin degrades to captured=False."""
    def boom(**k):
        raise camera.CameraError("no ffmpeg")
    monkeypatch.setattr(camera, "capture_frame", boom)
    out = vision.describe_frame(inputs={"reason": "x"}, context={"dry_run": False})
    assert out["captured"] is False
    assert "unavailable" in out["description"]


def test_camera_adapter_raises_cleanly_without_ffmpeg(monkeypatch):
    """The adapter raises CameraError, not a bare crash, when ffmpeg is missing."""
    monkeypatch.setattr(camera.shutil, "which", lambda name: None)
    with pytest.raises(camera.CameraError, match="ffmpeg"):
        camera.capture_frame()


# ─── the bundled worker must load ────────────────────────────────────────


def test_bundled_presence_glance_loads():
    path = BUILTIN_WORKERS / "presence-glance" / "worker.yaml"
    assert path.is_file(), "presence-glance must ship as a bundled reference worker"
    m = load(path)
    assert m.name == "presence-glance"
    assert set(m.permissions) == {"sensor:read", "camera:read"}
