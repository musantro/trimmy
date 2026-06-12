"""FFmpeg subprocess integration for video rendering."""

from __future__ import annotations

import contextlib
import json
import logging
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trimmy.presets import PLATFORM_PRESETS

logger = logging.getLogger(__name__)

_gpu_encoder_cache: str | None = None
_gpu_detection_done: bool = False

_NVENC_PRESET = {
    "slower": "p7",
    "slow": "p6",
    "medium": "p4",
    "fast": "p2",
    "veryfast": "p1",
}
_AMF_QUALITY = {
    "slower": "quality",
    "slow": "quality",
    "medium": "balanced",
    "fast": "speed",
    "veryfast": "speed",
}
_QSV_PRESET = {
    "slower": "veryslow",
    "slow": "slow",
    "medium": "medium",
    "fast": "fast",
    "veryfast": "veryfast",
}


@dataclass
class CropRect:
    """Rectangle describing a crop region in source-pixel coordinates."""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


class RenderContext:
    """Wraps FFmpeg subprocess execution with cancellation support."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._cancelled = False

    def cancel(self) -> None:
        """Signal cancellation and kill the running process."""
        with self._lock:
            self._cancelled = True
            if self._proc is not None:
                with contextlib.suppress(OSError):
                    self._proc.kill()

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str] | None:
        """Execute *cmd* and return the result, or ``None`` if cancelled."""
        with self._lock:
            if self._cancelled:
                return None
            self._proc = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        stdout, stderr = self._proc.communicate()
        with self._lock:
            returncode = self._proc.returncode
            self._proc = None
            if self._cancelled:
                return None
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)


def detect_gpu_encoder() -> str | None:
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
                timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        else:
            if proc.returncode == 0:
                _gpu_encoder_cache = enc
                logger.info("GPU encoder detected: %s", enc)
                break

    if _gpu_encoder_cache is None:
        logger.info("No GPU encoder available, will use libx264")
    return _gpu_encoder_cache


def _gpu_codec_args(
    encoder: str,
    preset: dict[str, Any],
) -> list[str] | None:
    cpu_preset: str = preset["preset"]
    crf: int = preset["crf"]

    if encoder == "h264_nvenc":
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            _NVENC_PRESET.get(cpu_preset, "p4"),
            "-cq",
            str(crf),
            "-b:v",
            "0",
        ]
    if encoder == "h264_amf":
        return [
            "-c:v",
            "h264_amf",
            "-quality",
            _AMF_QUALITY.get(cpu_preset, "balanced"),
            "-rc",
            "cqp",
            "-qp_i",
            str(crf),
            "-qp_p",
            str(crf),
            "-qp_b",
            str(crf),
        ]
    if encoder == "h264_qsv":
        return [
            "-c:v",
            "h264_qsv",
            "-preset",
            _QSV_PRESET.get(cpu_preset, "medium"),
            "-global_quality",
            str(crf),
        ]
    return None


def _cpu_codec_args(preset: dict[str, Any]) -> list[str]:
    return [
        "-c:v",
        "libx264",
        "-preset",
        preset["preset"],
        "-crf",
        str(preset["crf"]),
    ]


def _build_render_cmd(  # noqa: PLR0913
    src_path: Path,
    out_path: Path,
    trim_start: float,
    trim_end: float,
    filter_complex: str,
    codec_args: list[str],
    preset: dict[str, Any],
    maxrate: str,
    bufsize: str,
    *,
    gpu: bool = False,
) -> list[str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(trim_start),
        "-to",
        str(trim_end),
        "-i",
        str(src_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-map",
        "0:a?",
    ]
    cmd.extend(codec_args)
    level = "auto" if gpu else preset["level"]
    cmd.extend(
        [
            "-profile:v",
            preset["profile"],
            "-level:v",
            level,
            "-maxrate",
            maxrate,
            "-bufsize",
            bufsize,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            preset["audio_bitrate"],
            "-ac",
            "2",
            "-ar",
            "48000",
            "-movflags",
            preset["movflags"],
            "-shortest",
            str(out_path),
        ],
    )
    return cmd


def probe_video(path: Path) -> dict[str, Any]:
    """Run ffprobe and return duration, width, height, and fps."""
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
    )
    info = json.loads(proc.stdout)
    duration = float(info["format"]["duration"])
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    width = int(vs["width"])
    height = int(vs["height"])
    r_fps = vs.get("r_frame_rate", "30/1")
    num, den = (int(x) for x in r_fps.split("/"))
    fps = round(num / den, 3) if den else 30.0
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
    }


def render_video(  # noqa: PLR0913
    src_path: Path,
    out_path: Path,
    trim_start: float,
    trim_end: float,
    top_crop: CropRect,
    bottom_crop: CropRect,
    split_ratio: float,
    platform: str,
    quality: str,
    source_fps: float,
    ctx: RenderContext | None = None,
) -> dict[str, Any]:
    """Render a split-crop video using the given platform preset."""
    if ctx is None:
        ctx = RenderContext()
    preset = PLATFORM_PRESETS[platform][quality]
    output_width: int = preset["width"]
    output_height: int = preset["height"]

    top_out_h = int(output_height * split_ratio)
    bottom_out_h = output_height - top_out_h

    tx = int(top_crop.x)
    ty = int(top_crop.y)
    tw = int(top_crop.w)
    th = int(top_crop.h)
    bx = int(bottom_crop.x)
    by = int(bottom_crop.y)
    bw = int(bottom_crop.w)
    bh = int(bottom_crop.h)

    tw -= tw % 2
    th -= th % 2
    bw -= bw % 2
    bh -= bh % 2
    top_out_h -= top_out_h % 2
    bottom_out_h -= bottom_out_h % 2

    total_h = top_out_h + bottom_out_h
    if total_h != output_height:
        bottom_out_h += output_height - total_h

    max_fps: int = preset["max_fps"]
    fps_filter = f",fps={max_fps}" if source_fps > max_fps else ""
    output_fps = min(source_fps, float(max_fps))

    filter_complex = (
        f"[0:v]crop={tw}:{th}:{tx}:{ty},"
        f"scale={output_width}:{top_out_h}{fps_filter}[top];"
        f"[0:v]crop={bw}:{bh}:{bx}:{by},"
        f"scale={output_width}:{bottom_out_h}{fps_filter}[bottom];"
        f"[top][bottom]vstack=inputs=2[out]"
    )

    duration = trim_end - trim_start
    maxrate: str | None = preset.get("maxrate")
    bufsize: str | None = preset.get("bufsize")
    if maxrate is None and duration > 0:
        audio_bitrate: str = preset["audio_bitrate"]
        audio_kbps = int(audio_bitrate.replace("k", ""))
        max_size_mb: int = preset["max_size_mb"]
        total_kbps = (max_size_mb * 8 * 1024) / duration
        video_kbps = max(200, int(total_kbps - audio_kbps))
        maxrate = f"{video_kbps}k"
        bufsize_mult: int = preset["bufsize_mult"]
        bufsize = f"{video_kbps * bufsize_mult}k"

    gpu_enc = detect_gpu_encoder()

    if gpu_enc:
        gpu_args = _gpu_codec_args(gpu_enc, preset)
        assert gpu_args is not None  # noqa: S101
        assert maxrate is not None  # noqa: S101
        assert bufsize is not None  # noqa: S101
        cmd = _build_render_cmd(
            src_path,
            out_path,
            trim_start,
            trim_end,
            filter_complex,
            gpu_args,
            preset,
            maxrate,
            bufsize,
            gpu=True,
        )
        proc = ctx.run(cmd)
        if proc is None:
            return {"error": "Cancelled"}
        if proc.returncode == 0:
            file_size_mb = out_path.stat().st_size / (1024 * 1024)
            return {
                "size_mb": round(file_size_mb, 2),
                "resolution": f"{output_width}x{output_height}",
                "fps": output_fps,
                "encoder": gpu_enc,
            }
        logger.warning(
            "GPU encode failed (%s), falling back to libx264: %s",
            gpu_enc,
            proc.stderr[-500:],
        )

    if ctx.cancelled:
        return {"error": "Cancelled"}

    cpu_args = _cpu_codec_args(preset)
    assert maxrate is not None  # noqa: S101
    assert bufsize is not None  # noqa: S101
    cmd = _build_render_cmd(
        src_path,
        out_path,
        trim_start,
        trim_end,
        filter_complex,
        cpu_args,
        preset,
        maxrate,
        bufsize,
    )
    proc = ctx.run(cmd)
    if proc is None:
        return {"error": "Cancelled"}
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:]}

    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    return {
        "size_mb": round(file_size_mb, 2),
        "resolution": f"{output_width}x{output_height}",
        "fps": output_fps,
        "encoder": "libx264",
    }
