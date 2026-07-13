"""Tests for the ffmpeg infrastructure adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from trimmy.rendering.infrastructure import ffmpeg as ffmpeg_mod
from trimmy.rendering.infrastructure.ffmpeg import (
    FFmpegRenderingBackend,
    FFprobeVideoProber,
)


def test_backend_run_success():
    backend = FFmpegRenderingBackend()
    proc = MagicMock()
    proc.communicate.return_value = ("out", "err")
    proc.returncode = 0
    with patch.object(ffmpeg_mod.subprocess, "Popen", return_value=proc):
        result = backend.run(["echo", "hi"])
    assert result is not None
    assert result.returncode == 0
    assert result.stderr == "err"


def test_backend_cancel_before_run():
    backend = FFmpegRenderingBackend()
    backend.cancel()
    assert backend.cancelled is True
    assert backend.run(["echo", "hi"]) is None


def test_backend_cancel_during_run():
    backend = FFmpegRenderingBackend()
    proc = MagicMock()
    proc.returncode = -9

    def fake_communicate():
        backend.cancel()
        return ("", "")

    proc.communicate.side_effect = fake_communicate
    with patch.object(ffmpeg_mod.subprocess, "Popen", return_value=proc):
        assert backend.run(["sleep", "10"]) is None


def test_backend_detect_gpu_found():
    result = MagicMock()
    result.returncode = 0
    with patch.object(ffmpeg_mod.subprocess, "run", return_value=result):
        assert FFmpegRenderingBackend().detect_gpu_encoder() == "h264_nvenc"


def test_backend_detect_gpu_absent():
    result = MagicMock()
    result.returncode = 1
    with patch.object(ffmpeg_mod.subprocess, "run", return_value=result):
        assert FFmpegRenderingBackend().detect_gpu_encoder() is None


def test_backend_output_size_mb():
    backend = FFmpegRenderingBackend()
    path = MagicMock(spec=Path)
    path.stat.return_value.st_size = 10 * 1024 * 1024
    assert backend.output_size_mb(path) == 10.0


def test_ffprobe_reads_metadata():
    payload = json.dumps(
        {
            "format": {"duration": "120.5"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "60/1",
                },
                {
                    "codec_type": "audio",
                    "channels": 2,
                    "sample_rate": "48000",
                    "codec_name": "aac",
                },
            ],
        },
    )
    proc = MagicMock()
    proc.stdout = payload
    with patch.object(ffmpeg_mod.subprocess, "run", return_value=proc):
        metadata = FFprobeVideoProber().probe(Path("video.mp4"))
    assert metadata.duration == 120.5
    assert metadata.fps == 60.0
    assert metadata.width == 1920
    assert metadata.audio_channels == 2
    assert metadata.audio_sample_rate == 48000
    assert metadata.audio_codec == "aac"
