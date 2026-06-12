"""ffmpeg/ffprobe adapters implementing the render gateways."""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path

from trimmy.render.domain.gateways import RenderingBackend, VideoProber
from trimmy.render.domain.models import ProcessResult, VideoMetadata
from trimmy.shared.compat import override

logger = logging.getLogger(__name__)

_BYTES_PER_MB = 1024 * 1024
_GPU_PROBE_TIMEOUT = 15

_gpu_encoder_cache: str | None = None
_gpu_detection_done: bool = False


def _detect_gpu_encoder() -> str | None:
    """Probe for a hardware H.264 encoder and cache the result."""
    global _gpu_encoder_cache, _gpu_detection_done  # noqa: PLW0603
    if _gpu_detection_done:
        return _gpu_encoder_cache
    _gpu_detection_done = True

    for enc in ("h264_nvenc", "h264_amf", "h264_qsv"):
        try:
            proc = subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "ffmpeg",
                    "-hide_banner",
                    "-f",
                    "lavfi",
                    "-i",
                    "nullsrc=s=256x256:d=0.1",
                    "-frames:v",
                    "1",
                    "-c:v",
                    enc,
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                text=True,
                timeout=_GPU_PROBE_TIMEOUT,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):  # noqa: PERF203
            continue
        else:
            if proc.returncode == 0:
                _gpu_encoder_cache = enc
                logger.info("GPU encoder detected: %s", enc)
                break

    if _gpu_encoder_cache is None:
        logger.info("No GPU encoder available, will use libx264")
    return _gpu_encoder_cache


class FFmpegRenderingBackend(RenderingBackend):
    """Runs ffmpeg encodes in a cancellable subprocess."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._cancelled = False

    @property
    @override
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def cancel(self) -> None:
        """Signal cancellation and kill any running ffmpeg process."""
        with self._lock:
            self._cancelled = True
            if self._proc is not None:
                with contextlib.suppress(OSError):
                    self._proc.kill()

    @override
    def detect_gpu_encoder(self) -> str | None:
        """Return the available hardware encoder name, or ``None``."""
        return _detect_gpu_encoder()

    @override
    def run(self, command: Sequence[str]) -> ProcessResult | None:
        """Run *command*, returning its result or ``None`` if cancelled."""
        with self._lock:
            if self._cancelled:
                return None
            self._proc = subprocess.Popen(  # noqa: S603
                list(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        _, stderr = self._proc.communicate()
        with self._lock:
            returncode = self._proc.returncode
            self._proc = None
            if self._cancelled:
                return None
        return ProcessResult(returncode=returncode, stderr=stderr)

    @override
    def output_size_mb(self, path: Path) -> float:
        """Return the size of the rendered file at *path* in megabytes."""
        return round(path.stat().st_size / _BYTES_PER_MB, 2)


class FFprobeVideoProber(VideoProber):
    """Reads source metadata using ffprobe."""

    @override
    def probe(self, path: Path) -> VideoMetadata:
        """Return the probed metadata for the video at *path*."""
        proc = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        info = json.loads(proc.stdout)
        duration = float(info["format"]["duration"])
        vs = next(s for s in info["streams"] if s["codec_type"] == "video")
        r_fps = vs.get("r_frame_rate", "30/1")
        num, den = (int(x) for x in r_fps.split("/"))
        fps = round(num / den, 3) if den else 30.0
        return VideoMetadata(
            duration=duration,
            width=int(vs["width"]),
            height=int(vs["height"]),
            fps=fps,
        )
