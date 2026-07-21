"""The persisted user-preferences value object."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain import CropRect, CropSelection

DEFAULT_SPLIT_RATIO = 0.5
DEFAULT_VOLUME = 50


@dataclass(frozen=True)
class TargetPreference:
    """A persisted platform/format selection."""

    platform: str
    format_key: str


@dataclass(frozen=True)
class Preferences:
    """A snapshot of the user's editor settings."""

    selected_platform: str
    selected_format: str
    selected_quality: str
    split_ratio: float
    volume: int
    crops: CropSelection
    selected_targets: tuple[TargetPreference, ...] = ()
    last_video_folder: str = ""
    last_output_folder: str = ""

    @classmethod
    def default(cls) -> Preferences:
        """Return the built-in default preferences."""
        target = TargetPreference(platform="instagram", format_key="feed")
        return cls(
            selected_platform=target.platform,
            selected_format=target.format_key,
            selected_quality="max",
            split_ratio=DEFAULT_SPLIT_RATIO,
            volume=DEFAULT_VOLUME,
            crops=CropSelection(top=CropRect(), bottom=CropRect()),
            selected_targets=(target,),
            last_video_folder="",
            last_output_folder="",
        )
