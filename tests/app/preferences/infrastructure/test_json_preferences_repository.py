"""Tests for the JSON preferences repository."""

from __future__ import annotations

import json

from trimmy.app.preferences.domain.models import Preferences
from trimmy.app.preferences.infrastructure.json_preferences_repository import (
    JsonPreferencesRepository,
)
from trimmy.editing.shared.domain.models import CropRect, CropSelection


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
    assert prefs.last_video_folder == ""
    assert prefs.last_output_folder == ""


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
        last_video_folder=str(tmp_path / "source"),
        last_output_folder=str(tmp_path / "renders"),
    )
    repo.save(prefs)
    assert path.exists()
    assert repo.load() == prefs


def test_default_config_path_used_when_none():
    repo = JsonPreferencesRepository()
    assert repo._path.name == "config.json"
