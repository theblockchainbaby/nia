"""Camera adapter: capture a single frame from the default camera.

OS specific and dependency light. It shells out to ffmpeg (avfoundation on
macOS, v4l2 on Linux) so the core runtime takes on no new Python dependency,
consistent with Nia's two dependency rule. If ffmpeg or a camera is missing, it
raises CameraError with a clear message, which the vision builtin turns into a
graceful captured=False result rather than a crash. The capability is still
gated above this layer: nothing reaches here unless the manifest granted
camera:read and the worker's condition evaluated true.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class CameraError(RuntimeError):
    """Raised when a frame cannot be captured (no ffmpeg, no camera, or failure)."""


DEFAULT_CAPTURE_DIR = Path.home() / ".nia" / "captures"


def _ffmpeg_cmd(device: str, out_path: Path) -> list[str]:
    """Build the platform ffmpeg command to grab a single frame to out_path."""
    if sys.platform == "darwin":
        # avfoundation: video device index, no audio. Grab a few frames so the
        # sensor warms past the first dark frame; -update overwrites out_path so
        # the file ends up holding the last (warmer) frame.
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "avfoundation", "-framerate", "30", "-i", f"{device}:none",
            "-frames:v", "5", "-update", "1", str(out_path),
        ]
    # Linux v4l2
    dev = device if device.startswith("/dev/") else f"/dev/video{device}"
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "v4l2", "-i", dev, "-frames:v", "1", str(out_path),
    ]


def capture_frame(*, device: str = "0", output_dir: Path | None = None,
                  timeout: int = 20) -> dict:
    """Capture one frame from the camera to a file and return capture metadata.

    Returns {"captured": True, "path", "device", "captured_at", "bytes"}.

    Raises CameraError if ffmpeg is unavailable, the platform is unsupported, the
    camera cannot be opened, or no frame is produced.
    """
    if shutil.which("ffmpeg") is None:
        raise CameraError(
            "ffmpeg not found. Install it (brew install ffmpeg) to enable capture."
        )
    if sys.platform not in ("darwin", "linux"):
        raise CameraError(f"camera capture not supported on {sys.platform!r}")

    out_dir = Path(output_dir) if output_dir else DEFAULT_CAPTURE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_path = out_dir / f"frame_{stamp}.jpg"

    cmd = _ffmpeg_cmd(device, out_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise CameraError(f"camera capture timed out after {timeout}s") from e
    except FileNotFoundError as e:
        raise CameraError("ffmpeg not found on PATH") from e

    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        last = (proc.stderr or "").strip().splitlines()
        raise CameraError(f"camera capture failed: {last[-1] if last else 'unknown error'}")

    return {
        "captured": True,
        "path": str(out_path),
        "device": device,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "bytes": out_path.stat().st_size,
    }
