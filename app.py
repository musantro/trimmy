import json
import subprocess
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

PLATFORM_PRESETS = {
    "whatsapp": {
        "max": {
            "width": 720, "height": 1280,
            "profile": "main", "level": "3.1", "preset": "slow",
            "crf": 20, "maxrate": None, "bufsize_mult": 2,
            "max_fps": 30, "audio_bitrate": "128k",
            "max_size_mb": 16, "movflags": "+faststart",
        },
        "optimized": {
            "width": 720, "height": 1280,
            "profile": "main", "level": "3.1", "preset": "medium",
            "crf": 26, "maxrate": None, "bufsize_mult": 2,
            "max_fps": 30, "audio_bitrate": "96k",
            "max_size_mb": 16, "movflags": "+faststart",
        },
    },
    "twitter": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 18, "maxrate": "15000k", "bufsize": "30000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 512, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "medium",
            "crf": 23, "maxrate": "5000k", "bufsize": "10000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 512, "movflags": "+faststart",
        },
    },
    "instagram": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.0", "preset": "slow",
            "crf": 16, "maxrate": "25000k", "bufsize": "50000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 300, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.0", "preset": "medium",
            "crf": 23, "maxrate": "8000k", "bufsize": "16000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 300, "movflags": "+faststart",
        },
    },
    "telegram": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 18, "maxrate": "20000k", "bufsize": "40000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 2048, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "main", "level": "4.0", "preset": "medium",
            "crf": 23, "maxrate": "6000k", "bufsize": "12000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 2048, "movflags": "+faststart",
        },
    },
    "tiktok": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 16, "maxrate": "20000k", "bufsize": "40000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 4096, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "medium",
            "crf": 23, "maxrate": "8000k", "bufsize": "16000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 4096, "movflags": "+faststart",
        },
    },
}


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path("static/index.html").read_text(encoding="utf-8")


@app.get("/presets")
async def get_presets():
    return {k: {"width": v["width"], "height": v["height"], "max_size_mb": v["max_size_mb"]}
            for k, v in PLATFORM_PRESETS.items()}


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    file_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{file_id}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    probe = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(dest),
        ],
        capture_output=True, text=True,
    )

    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    width = int(video_stream["width"])
    height = int(video_stream["height"])

    r_fps = video_stream.get("r_frame_rate", "30/1")
    num, den = (int(x) for x in r_fps.split("/"))
    fps = round(num / den, 3) if den else 30

    return {
        "id": file_id,
        "filename": file.filename,
        "ext": ext,
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
    }


@app.get("/video/{file_id}")
async def serve_video(file_id: str):
    for f in UPLOAD_DIR.iterdir():
        if f.stem == file_id:
            media_type = "video/x-matroska" if f.suffix == ".mkv" else f"video/{f.suffix[1:]}"
            return FileResponse(f, media_type=media_type)
    return JSONResponse({"error": "not found"}, status_code=404)


@app.post("/render")
async def render_video(
    file_id: str = Form(...),
    ext: str = Form(...),
    trim_start: float = Form(...),
    trim_end: float = Form(...),
    src_width: int = Form(...),
    src_height: int = Form(...),
    top_x: float = Form(...),
    top_y: float = Form(...),
    top_w: float = Form(...),
    top_h: float = Form(...),
    bottom_x: float = Form(...),
    bottom_y: float = Form(...),
    bottom_w: float = Form(...),
    bottom_h: float = Form(...),
    split_ratio: float = Form(...),
    platform: str = Form("instagram"),
    quality: str = Form("max"),
    source_fps: float = Form(30.0),
):
    src_path = UPLOAD_DIR / f"{file_id}{ext}"
    if not src_path.exists():
        return JSONResponse({"error": "source not found"}, status_code=404)

    platform_presets = PLATFORM_PRESETS.get(platform)
    if not platform_presets:
        return JSONResponse({"error": f"unknown platform: {platform}"}, status_code=400)
    preset = platform_presets.get(quality, platform_presets["max"])

    output_width = preset["width"]
    output_height = preset["height"]

    out_id = uuid.uuid4().hex
    out_path = OUTPUT_DIR / f"{out_id}.mp4"

    top_out_h = int(output_height * split_ratio)
    bottom_out_h = output_height - top_out_h

    tx, ty, tw, th = int(top_x), int(top_y), int(top_w), int(top_h)
    bx, by, bw, bh = int(bottom_x), int(bottom_y), int(bottom_w), int(bottom_h)

    # Even dimensions
    tw -= tw % 2
    th -= th % 2
    bw -= bw % 2
    bh -= bh % 2
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

    # Compute maxrate for WhatsApp (fit in 16 MB)
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
        "-ss", str(trim_start),
        "-to", str(trim_end),
        "-i", str(src_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",
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
        "-ac", "2",
        "-ar", "48000",
        "-movflags", preset["movflags"],
        "-shortest",
        str(out_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return JSONResponse({"error": proc.stderr[-2000:]}, status_code=500)

    file_size_mb = out_path.stat().st_size / (1024 * 1024)

    return {
        "url": f"/outputs/{out_id}.mp4",
        "filename": f"{out_id}.mp4",
        "size_mb": round(file_size_mb, 2),
        "platform": platform,
        "resolution": f"{output_width}x{output_height}",
        "fps": output_fps,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
