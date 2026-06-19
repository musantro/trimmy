"""Object mothers / builders for the test suite."""

from __future__ import annotations

from pathlib import Path

from trimmy.editing.shared.domain.models import (
    CropRect,
    CropSelection,
    SourceSize,
    TrimRange,
)
from trimmy.rendering.domain.models import EncoderPreset, RenderSpec


def make_source(width: int = 1920, height: int = 1080) -> SourceSize:
    """Build a source size."""
    return SourceSize(width=width, height=height)


def make_crop(
    x: float = 0.0,
    y: float = 0.0,
    w: float = 100.0,
    h: float = 100.0,
) -> CropRect:
    """Build a crop rectangle."""
    return CropRect(x=x, y=y, w=w, h=h)


def make_selection(
    top: CropRect | None = None,
    bottom: CropRect | None = None,
) -> CropSelection:
    """Build a crop selection."""
    return CropSelection(
        top=top or make_crop(0, 0, 500, 400),
        bottom=bottom or make_crop(100, 500, 500, 400),
    )


def make_preset(
    width: int = 1080,
    height: int = 1920,
    profile: str = "high",
    level: str = "4.0",
    preset: str = "slow",
    crf: int = 16,
    max_fps: int = 60,
    audio_bitrate: str = "192k",
    max_size_mb: int = 300,
    movflags: str = "+faststart",
    maxrate: str | None = "25000k",
    bufsize: str | None = "50000k",
    bufsize_mult: int | None = None,
) -> EncoderPreset:
    """Build an encoder preset."""
    return EncoderPreset(
        width=width,
        height=height,
        profile=profile,
        level=level,
        preset=preset,
        crf=crf,
        max_fps=max_fps,
        audio_bitrate=audio_bitrate,
        max_size_mb=max_size_mb,
        movflags=movflags,
        maxrate=maxrate,
        bufsize=bufsize,
        bufsize_mult=bufsize_mult,
    )


def make_spec(
    platform: str = "instagram",
    quality: str = "max",
    trim: TrimRange | None = None,
    crops: CropSelection | None = None,
    split_ratio: float = 0.5,
    source_fps: float = 30.0,
    output_path: Path | None = None,
) -> RenderSpec:
    """Build a render spec."""
    return RenderSpec(
        source_path=Path("input.mp4"),
        output_path=output_path or Path("output.mp4"),
        trim=trim or TrimRange(0.0, 10.0),
        crops=crops or make_selection(),
        split_ratio=split_ratio,
        platform=platform,
        quality=quality,
        source_fps=source_fps,
    )
