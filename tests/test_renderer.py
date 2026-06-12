import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.mothers import make_crop_rect, make_preset
from trimmy.renderer import (
    CropRect,
    RenderContext,
    _build_render_cmd,
    _cpu_codec_args,
    _gpu_codec_args,
    detect_gpu_encoder,
    probe_video,
    render_video,
)


def test_crop_rect_defaults():
    cr = CropRect()
    assert cr.x == 0.0
    assert cr.y == 0.0
    assert cr.w == 0.0
    assert cr.h == 0.0


def test_crop_rect_custom_values():
    cr = CropRect(x=10.0, y=20.0, w=300.0, h=400.0)
    assert cr.x == 10.0
    assert cr.y == 20.0
    assert cr.w == 300.0
    assert cr.h == 400.0


def test_render_context_run_success():
    ctx = RenderContext()
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("out", "err")
    mock_proc.returncode = 0
    with patch("trimmy.renderer.subprocess.Popen", return_value=mock_proc):
        result = ctx.run(["echo", "hello"])
    assert result is not None
    assert result.returncode == 0
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_render_context_cancel_before_run():
    ctx = RenderContext()
    ctx.cancel()
    assert ctx.cancelled is True
    result = ctx.run(["echo", "hello"])
    assert result is None


def test_render_context_cancel_during_run():
    ctx = RenderContext()
    mock_proc = MagicMock()
    mock_proc.returncode = -9

    def fake_communicate():
        ctx.cancel()
        return ("", "")

    mock_proc.communicate.side_effect = fake_communicate
    with patch("trimmy.renderer.subprocess.Popen", return_value=mock_proc):
        result = ctx.run(["sleep", "10"])
    assert result is None


def test_detect_gpu_encoder_finds_nvenc():
    fake_result = MagicMock()
    fake_result.returncode = 0
    with patch("trimmy.renderer.subprocess.run", return_value=fake_result):
        enc = detect_gpu_encoder()
    assert enc == "h264_nvenc"


def test_detect_gpu_encoder_no_gpu():
    fake_result = MagicMock()
    fake_result.returncode = 1
    with patch("trimmy.renderer.subprocess.run", return_value=fake_result):
        enc = detect_gpu_encoder()
    assert enc is None


def test_gpu_codec_args_nvenc():
    preset = make_preset()
    args = _gpu_codec_args("h264_nvenc", preset)
    assert args is not None
    assert "-c:v" in args
    assert "h264_nvenc" in args
    assert "-cq" in args
    assert "-preset" in args


def test_gpu_codec_args_amf():
    preset = make_preset()
    args = _gpu_codec_args("h264_amf", preset)
    assert args is not None
    assert "h264_amf" in args
    assert "-quality" in args
    assert "-rc" in args
    assert "cqp" in args


def test_gpu_codec_args_qsv():
    preset = make_preset()
    args = _gpu_codec_args("h264_qsv", preset)
    assert args is not None
    assert "h264_qsv" in args
    assert "-global_quality" in args


def test_gpu_codec_args_unknown():
    preset = make_preset()
    result = _gpu_codec_args("h264_unknown", preset)
    assert result is None


def test_cpu_codec_args():
    preset = make_preset(preset="slow", crf=16)
    args = _cpu_codec_args(preset)
    assert args == ["-c:v", "libx264", "-preset", "slow", "-crf", "16"]


def test_build_render_cmd_cpu():
    preset = make_preset()
    codec_args = ["-c:v", "libx264", "-preset", "slow", "-crf", "16"]
    cmd = _build_render_cmd(
        Path("input.mp4"),
        Path("output.mp4"),
        0.0,
        10.0,
        "[0:v]crop=100:100:0:0[out]",
        codec_args,
        preset,
        "25000k",
        "50000k",
    )
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-level:v" in cmd
    idx = cmd.index("-level:v")
    assert cmd[idx + 1] == "4.0"


def test_build_render_cmd_gpu():
    preset = make_preset()
    codec_args = ["-c:v", "h264_nvenc", "-preset", "p6"]
    cmd = _build_render_cmd(
        Path("input.mp4"),
        Path("output.mp4"),
        0.0,
        10.0,
        "[0:v]crop=100:100:0:0[out]",
        codec_args,
        preset,
        "25000k",
        "50000k",
        gpu=True,
    )
    idx = cmd.index("-level:v")
    assert cmd[idx + 1] == "auto"


def test_probe_video():
    ffprobe_output = json.dumps(
        {
            "format": {"duration": "120.5"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "60/1",
                },
                {"codec_type": "audio"},
            ],
        }
    )
    fake_proc = MagicMock()
    fake_proc.stdout = ffprobe_output
    with patch("trimmy.renderer.subprocess.run", return_value=fake_proc):
        info = probe_video(Path("test.mp4"))
    assert info["duration"] == 120.5
    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["fps"] == 60.0


def test_render_video_cpu_success():
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stderr = ""
    ctx.run.return_value = fake_proc

    out_path = MagicMock(spec=Path)
    out_path.stat.return_value.st_size = 10 * 1024 * 1024  # 10 MB

    with patch("trimmy.renderer.detect_gpu_encoder", return_value=None):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=out_path,
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="instagram",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert "error" not in result
    assert result["size_mb"] == 10.0
    assert result["encoder"] == "libx264"
    assert result["resolution"] == "1080x1920"


def test_render_video_cancelled():
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = True
    ctx.run.return_value = None

    with patch("trimmy.renderer.detect_gpu_encoder", return_value=None):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=Path("output.mp4"),
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="instagram",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert result == {"error": "Cancelled"}


def test_render_video_gpu_success():
    """GPU encoder succeeds on first try."""
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stderr = ""
    ctx.run.return_value = fake_proc

    out_path = MagicMock(spec=Path)
    out_path.stat.return_value.st_size = 5 * 1024 * 1024

    with patch("trimmy.renderer.detect_gpu_encoder", return_value="h264_nvenc"):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=out_path,
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="instagram",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert result["encoder"] == "h264_nvenc"
    assert "error" not in result


def test_render_video_gpu_fail_cpu_fallback():
    """GPU encoder fails, falls back to CPU."""
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    gpu_proc = MagicMock()
    gpu_proc.returncode = 1
    gpu_proc.stderr = "GPU error"

    cpu_proc = MagicMock()
    cpu_proc.returncode = 0

    ctx.run.side_effect = [gpu_proc, cpu_proc]

    out_path = MagicMock(spec=Path)
    out_path.stat.return_value.st_size = 8 * 1024 * 1024

    with patch("trimmy.renderer.detect_gpu_encoder", return_value="h264_nvenc"):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=out_path,
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="instagram",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert result["encoder"] == "libx264"
    assert "error" not in result


def test_render_video_cpu_error():
    """CPU encode returns non-zero exit code."""
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    fake_proc = MagicMock()
    fake_proc.returncode = 1
    fake_proc.stderr = "Encoding error details"
    ctx.run.return_value = fake_proc

    with patch("trimmy.renderer.detect_gpu_encoder", return_value=None):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=Path("output.mp4"),
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="instagram",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert "error" in result


def test_render_video_whatsapp_dynamic_bitrate():
    """WhatsApp preset with maxrate=None triggers dynamic bitrate calculation."""
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    ctx.run.return_value = fake_proc

    out_path = MagicMock(spec=Path)
    out_path.stat.return_value.st_size = 5 * 1024 * 1024

    with patch("trimmy.renderer.detect_gpu_encoder", return_value=None):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=out_path,
            trim_start=0.0,
            trim_end=30.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="whatsapp",
            quality="max",
            source_fps=30.0,
            ctx=ctx,
        )
    assert "error" not in result
    assert result["encoder"] == "libx264"


def test_render_video_fps_capping():
    """Source FPS exceeding max_fps triggers fps_filter."""
    top_crop = make_crop_rect(x=0, y=0, w=500, h=400)
    bot_crop = make_crop_rect(x=100, y=500, w=500, h=400)

    ctx = MagicMock(spec=RenderContext)
    ctx.cancelled = False

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    ctx.run.return_value = fake_proc

    out_path = MagicMock(spec=Path)
    out_path.stat.return_value.st_size = 5 * 1024 * 1024

    # WhatsApp max_fps is 30, source is 120
    with patch("trimmy.renderer.detect_gpu_encoder", return_value=None):
        result = render_video(
            src_path=Path("input.mp4"),
            out_path=out_path,
            trim_start=0.0,
            trim_end=10.0,
            top_crop=top_crop,
            bottom_crop=bot_crop,
            split_ratio=0.5,
            platform="whatsapp",
            quality="max",
            source_fps=120.0,
            ctx=ctx,
        )
    assert result["fps"] == 30


@pytest.mark.parametrize(
    "cpu_preset,expected_nvenc",
    [
        ("slower", "p7"),
        ("slow", "p6"),
        ("medium", "p4"),
        ("fast", "p2"),
        ("veryfast", "p1"),
    ],
)
def test_nvenc_preset_mapping(cpu_preset, expected_nvenc):
    preset = make_preset(preset=cpu_preset)
    args = _gpu_codec_args("h264_nvenc", preset)
    assert args is not None
    idx = args.index("-preset")
    assert args[idx + 1] == expected_nvenc


@pytest.mark.parametrize(
    "cpu_preset,expected_quality",
    [
        ("slower", "quality"),
        ("slow", "quality"),
        ("medium", "balanced"),
        ("fast", "speed"),
        ("veryfast", "speed"),
    ],
)
def test_amf_quality_mapping(cpu_preset, expected_quality):
    preset = make_preset(preset=cpu_preset)
    args = _gpu_codec_args("h264_amf", preset)
    assert args is not None
    idx = args.index("-quality")
    assert args[idx + 1] == expected_quality
