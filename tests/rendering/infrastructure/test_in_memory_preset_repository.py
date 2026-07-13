"""Tests for the in-memory preset repository."""

from __future__ import annotations

import pytest

from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)

ALL_PLATFORMS = ["instagram", "tiktok", "twitter", "whatsapp", "telegram"]


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
