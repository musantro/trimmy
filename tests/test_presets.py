import pytest

from trimmy.presets import PLATFORM_FORMATS, PLATFORM_INFO, PLATFORM_PRESETS

ALL_PLATFORMS = list(PLATFORM_PRESETS.keys())
QUALITIES = ["max", "optimized"]
REQUIRED_PRESET_KEYS = {
    "width",
    "height",
    "profile",
    "level",
    "preset",
    "crf",
    "max_fps",
    "audio_bitrate",
    "max_size_mb",
    "movflags",
}
REQUIRED_FORMAT_KEYS = {"key", "label", "max_duration"}


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_all_platforms_have_both_qualities(platform):
    assert "max" in PLATFORM_PRESETS[platform]
    assert "optimized" in PLATFORM_PRESETS[platform]


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
@pytest.mark.parametrize("quality", QUALITIES)
def test_preset_has_required_keys(platform, quality):
    preset = PLATFORM_PRESETS[platform][quality]
    missing = REQUIRED_PRESET_KEYS - set(preset.keys())
    assert not missing, f"Missing keys in {platform}/{quality}: {missing}"


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_platform_info_matches_presets(platform):
    assert platform in PLATFORM_INFO
    for quality in QUALITIES:
        assert quality in PLATFORM_INFO[platform]


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_platform_formats_has_required_keys(platform):
    formats = PLATFORM_FORMATS[platform]
    for fmt in formats:
        missing = REQUIRED_FORMAT_KEYS - set(fmt.keys())
        assert not missing, f"Missing keys in {platform} format {fmt}: {missing}"


@pytest.mark.parametrize("platform", ALL_PLATFORMS)
def test_all_platforms_have_formats(platform):
    assert len(PLATFORM_FORMATS[platform]) >= 1
