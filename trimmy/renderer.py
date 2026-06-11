import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from trimmy.presets import PLATFORM_PRESETS

logger = logging.getLogger(__name__)

_gpu_encoder_cache = None
_gpu_detection_done = False

_NVENC_PRESET = {"slower": "p7", "slow": "p6", "medium": "p4", "fast": "p2", "veryfast": "p1"}
_AMF_QUALITY = {"slower": "quality", "slow": "quality", "medium": "balanced", "fast": "speed", "veryfast": "speed"}
_QSV_PRESET = {"slower": "veryslow", "slow": "slow", "medium": "medium", "fast": "fast", "veryfast": "veryfast"}


@dataclass
class CropRect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


def detect_gpu_encoder():
    global _gpu_encoder_cache, _gpu_detection_done
    if _gpu_detection_done:
        return _gpu_encoder_cache
    _gpu_detection_done = True

    for enc in ("h264_nvenc", "h264_amf", "h264_qsv"):
        try:
            proc = subprocess.run(
                ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i",
                 "nullsrc=s=256x256:d=0.1", "-frames:v", "1",
                 "-c:v", enc, "-f", "null", "-"],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0:
                _gpu_encoder_cache = enc
                logger.info("GPU encoder detected: %s", enc)
                break
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    if _gpu_encoder_cache is None:
        logger.info("No GPU encoder available, will use libx264")
    return _gpu_encoder_cache


def _gpu_codec_args(encoder, preset):
    cpu_preset = preset["preset"]
    crf = preset["crf"]

    if encoder == "h264_nvenc":
        return [
            "-c:v", "h264_nvenc",
            "-preset", _NVENC_PRESET.get(cpu_preset, "p4"),
            "-cq", str(crf),
            "-b:v", "0",
        ]
    if encoder == "h264_amf":
        return [
            "-c:v", "h264_amf",
            "-quality", _AMF_QUALITY.get(cpu_preset, "balanced"),
            "-rc", "cqp",
            "-qp_i", str(crf),
            "-qp_p", str(crf),
            "-qp_b", str(crf),
        ]
    if encoder == "h264_qsv":
        return [
            "-c:v", "h264_qsv",
            "-preset", _QSV_PRESET.get(cpu_preset, "medium"),
            "-global_quality", str(crf),
        ]
    return None


def _cpu_codec_args(preset):
    return [
        "-c:v", "libx264",
        "-preset", preset["preset"],
        "-crf", str(preset["crf"]),
    ]


def _build_render_cmd(src_path, out_path, trim_start, trim_end,
                      filter_complex, codec_args, preset, maxrate, bufsize):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(trim_start), "-to", str(trim_end),
        "-i", str(src_path),
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a?",
    ]
    cmd.extend(codec_args)
    cmd.extend([
        "-profile:v", preset["profile"],
        "-level:v", preset["level"],
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", preset["audio_bitrate"],
        "-ac", "2", "-ar", "48000",
        "-movflags", preset["movflags"],
        "-shortest",
        str(out_path),
    ])
    return cmd


def probe_video(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True,
    )
    info = json.loads(proc.stdout)
    duration = float(info["format"]["duration"])
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    width = int(vs["width"])
    height = int(vs["height"])
    r_fps = vs.get("r_frame_rate", "30/1")
    num, den = (int(x) for x in r_fps.split("/"))
    fps = round(num / den, 3) if den else 30.0
    return {"duration": duration, "width": width, "height": height, "fps": fps}


def render_video(
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
) -> dict:
    preset = PLATFORM_PRESETS[platform][quality]
    output_width = preset["width"]
    output_height = preset["height"]

    top_out_h = int(output_height * split_ratio)
    bottom_out_h = output_height - top_out_h

    tx, ty, tw, th = int(top_crop.x), int(top_crop.y), int(top_crop.w), int(top_crop.h)
    bx, by, bw, bh = int(bottom_crop.x), int(bottom_crop.y), int(bottom_crop.w), int(bottom_crop.h)

    tw -= tw % 2; th -= th % 2
    bw -= bw % 2; bh -= bh % 2
    top_out_h -= top_out_h % 2
    bottom_out_h -= bottom_out_h % 2

    total_h = top_out_h + bottom_out_h
    if total_h != output_height:
        bottom_out_h += output_height - total_h

    max_fps = preset["max_fps"]
    fps_filter = f",fps={max_fps}" if source_fps > max_fps else ""
    output_fps = min(source_fps, max_fps)

    filter_complex = (
        f"[0:v]crop={tw}:{th}:{tx}:{ty},scale={output_width}:{top_out_h}{fps_filter}[top];"
        f"[0:v]crop={bw}:{bh}:{bx}:{by},scale={output_width}:{bottom_out_h}{fps_filter}[bottom];"
        f"[top][bottom]vstack=inputs=2[out]"
    )

    duration = trim_end - trim_start
    maxrate = preset.get("maxrate")
    bufsize = preset.get("bufsize")
    if maxrate is None and duration > 0:
        audio_kbps = int(preset["audio_bitrate"].replace("k", ""))
        total_kbps = (preset["max_size_mb"] * 8 * 1024) / duration
        video_kbps = max(200, int(total_kbps - audio_kbps))
        maxrate = f"{video_kbps}k"
        bufsize = f"{video_kbps * preset['bufsize_mult']}k"

    gpu_enc = detect_gpu_encoder()

    if gpu_enc:
        gpu_args = _gpu_codec_args(gpu_enc, preset)
        cmd = _build_render_cmd(src_path, out_path, trim_start, trim_end,
                                filter_complex, gpu_args, preset, maxrate, bufsize)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            file_size_mb = out_path.stat().st_size / (1024 * 1024)
            return {
                "size_mb": round(file_size_mb, 2),
                "resolution": f"{output_width}x{output_height}",
                "fps": output_fps,
                "encoder": gpu_enc,
            }
        logger.warning("GPU encode failed (%s), falling back to libx264: %s",
                       gpu_enc, proc.stderr[-500:])

    cpu_args = _cpu_codec_args(preset)
    cmd = _build_render_cmd(src_path, out_path, trim_start, trim_end,
                            filter_complex, cpu_args, preset, maxrate, bufsize)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:]}

    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    return {
        "size_mb": round(file_size_mb, 2),
        "resolution": f"{output_width}x{output_height}",
        "fps": output_fps,
        "encoder": "libx264",
    }
