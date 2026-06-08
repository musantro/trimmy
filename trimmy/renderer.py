import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from video_trimmer.presets import PLATFORM_PRESETS


@dataclass
class CropRect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


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

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(trim_start), "-to", str(trim_end),
        "-i", str(src_path),
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264",
        "-profile:v", preset["profile"],
        "-level:v", preset["level"],
        "-preset", preset["preset"],
        "-crf", str(preset["crf"]),
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", preset["audio_bitrate"],
        "-ac", "2", "-ar", "48000",
        "-movflags", preset["movflags"],
        "-shortest",
        str(out_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": proc.stderr[-2000:]}

    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    return {
        "size_mb": round(file_size_mb, 2),
        "resolution": f"{output_width}x{output_height}",
        "fps": output_fps,
    }
