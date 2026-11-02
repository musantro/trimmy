"""Tests for the ffmpeg infrastructure adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trimmy.rendering.infrastructure import ffmpeg as ffmpeg_mod
from trimmy.rendering.infrastructure.ffmpeg import (
    FFmpegRenderingBackend,
    FFprobeVideoProber,
)


def test_backend_run_success(tmp_path):
    backend = FFmpegRenderingBackend()
    proc = MagicMock()
    proc.communicate.return_value = ("out", "err")
    proc.returncode = 0

    def launch(command, **kwargs):
        Path(command[-1]).write_text("complete")
        return proc

    with patch.object(ffmpeg_mod.subprocess, "Popen", side_effect=launch):
        result = backend.run(["ffmpeg", str(tmp_path / "out.mp4")])
    assert (tmp_path / "out.mp4").read_text() == "complete"
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


def test_existing_output_is_never_overwritten(tmp_path):
    path = tmp_path / "existing.mp4"
    path.write_bytes(b"completed")
    backend = FFmpegRenderingBackend()
    with patch.object(ffmpeg_mod.subprocess, "Popen") as launch:
        result = backend.run(["ffmpeg", str(path)])
    assert result is not None
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert path.read_bytes() == b"completed"
    launch.assert_not_called()


def test_cancel_without_partial_file_is_safe(tmp_path):
    backend = FFmpegRenderingBackend()
    proc = MagicMock()

    def communicate():
        backend.cancel()
        return "", ""

    proc.communicate.side_effect = communicate
    with patch.object(ffmpeg_mod.subprocess, "Popen", return_value=proc):
        assert backend.run(["ffmpeg", str(tmp_path / "out.mp4")]) is None
    assert list(tmp_path.iterdir()) == []


def test_cleanup_error_is_surfaced(tmp_path):
    backend = FFmpegRenderingBackend()
    with (
        patch.object(backend, "_run_process", return_value=None),
        patch.object(
            Path,
            "unlink",
            side_effect=PermissionError("locked"),
        ),
    ):
        result = backend.run(["ffmpeg", str(tmp_path / "out.mp4")])
    assert result is not None
    assert result.returncode != 0
    assert "Cleanup failed" in result.stderr
    assert "locked" in result.stderr


@pytest.mark.parametrize(
    "error", [FileNotFoundError("encoder missing"), OSError("disk full")]
)
def test_backend_launch_error_is_a_reportable_failure(tmp_path, error):
    with patch.object(ffmpeg_mod.subprocess, "Popen", side_effect=error):
        result = FFmpegRenderingBackend().run(["ffmpeg", str(tmp_path / "out.mp4")])
    assert result is not None
    assert result.returncode != 0
    assert str(error) in result.stderr


def test_publication_without_hardlinks_is_exclusive_and_cleans_failed_copy(tmp_path):
    temporary = tmp_path / "staging.mp4"
    destination = tmp_path / "output.mp4"
    temporary.write_bytes(b"finished")
    with patch.object(Path, "hardlink_to", side_effect=OSError("unsupported")):
        FFmpegRenderingBackend._publish_output(temporary, destination)
        assert destination.read_bytes() == b"finished"
        with pytest.raises(FileExistsError):
            FFmpegRenderingBackend._publish_output(temporary, destination)
        assert destination.read_bytes() == b"finished"
        destination.unlink()
        with (
            patch.object(ffmpeg_mod.shutil, "copyfileobj", side_effect=OSError("full")),
            pytest.raises(OSError),
        ):
            FFmpegRenderingBackend._publish_output(temporary, destination)
        assert not destination.exists()
        temporary.unlink()
        with pytest.raises(FileNotFoundError):
            FFmpegRenderingBackend._publish_output(temporary, destination)
        assert not destination.exists()


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
