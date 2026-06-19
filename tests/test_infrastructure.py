"""Tests for the infrastructure adapters (omitted from the coverage gate)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trimmy.crop.domain.models import CropRect, CropSelection
from trimmy.preferences.domain.models import Preferences
from trimmy.preferences.infrastructure.json_preferences_repository import (
    JsonPreferencesRepository,
)
from trimmy.render.infrastructure import ffmpeg as ffmpeg_mod
from trimmy.render.infrastructure.ffmpeg import (
    FFmpegRenderingBackend,
    FFprobeVideoProber,
)
from trimmy.render.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)

ALL_PLATFORMS = ["instagram", "tiktok", "twitter", "whatsapp", "telegram"]


# ---- preset repository ----


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_preset_repository_serves_catalogue(platform):
    repo = InMemoryPresetRepository()
    for quality in ("max", "optimized"):
        preset = repo.encoder_preset(platform, quality)
        assert preset.width > 0
        info = repo.display_info(platform, quality)
        assert info.res
    assert len(repo.formats(platform)) >= 1


def test_whatsapp_preset_is_dynamic():
    preset = InMemoryPresetRepository().encoder_preset("whatsapp", "max")
    assert preset.maxrate is None
    assert preset.bufsize_mult == 2


# ---- json preferences repository ----


def test_json_repo_returns_defaults_when_missing(tmp_path):
    repo = JsonPreferencesRepository(tmp_path / "config.json")
    assert repo.load() == Preferences.default()


def test_json_repo_returns_defaults_on_corrupt_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert JsonPreferencesRepository(path).load() == Preferences.default()


def test_json_repo_merges_partial_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"selected_platform": "tiktok"}), encoding="utf-8")
    prefs = JsonPreferencesRepository(path).load()
    assert prefs.selected_platform == "tiktok"
    assert prefs.selected_quality == "max"


def test_json_repo_roundtrip(tmp_path):
    path = tmp_path / "nested" / "config.json"
    repo = JsonPreferencesRepository(path)
    prefs = Preferences(
        selected_platform="twitter",
        selected_format="post",
        selected_quality="optimized",
        split_ratio=0.7,
        volume=80,
        crops=CropSelection(
            top=CropRect(10, 20, 500, 400),
            bottom=CropRect(30, 40, 600, 500),
        ),
    )
    repo.save(prefs)
    assert path.exists()
    assert repo.load() == prefs


def test_default_config_path_used_when_none():
    repo = JsonPreferencesRepository()
    assert repo._path.name == "config.json"


# ---- ffmpeg backend ----


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


# ---- ffprobe ----


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
                {"codec_type": "audio"},
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
