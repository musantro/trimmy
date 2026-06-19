"""Shared fixtures for the test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_gpu_cache():
    """Reset the ffmpeg GPU detection cache between tests."""
    import trimmy.rendering.infrastructure.ffmpeg as ffmpeg_mod

    ffmpeg_mod._gpu_encoder_cache = None
    ffmpeg_mod._gpu_detection_done = False
    yield
    ffmpeg_mod._gpu_encoder_cache = None
    ffmpeg_mod._gpu_detection_done = False
