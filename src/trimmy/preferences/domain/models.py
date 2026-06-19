"""The persisted user-preferences value object."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.crop.domain.models import CropRect, CropSelection

DEFAULT_SPLIT_RATIO = 0.5
DEFAULT_VOLUME = 50


@dataclass(frozen=True)
class Preferences:
    """A snapshot of the user's editor settings."""

    selected_platform: str
    selected_format: str
    selected_quality: str
    split_ratio: float
    volume: int
    crops: CropSelection

    @classmethod
    def default(cls) -> Preferences:
        """Return the built-in default preferences."""
        return cls(
            selected_platform="instagram",
            selected_format="feed",
            selected_quality="max",
            split_ratio=DEFAULT_SPLIT_RATIO,
            volume=DEFAULT_VOLUME,
            crops=CropSelection(top=CropRect(), bottom=CropRect()),
        )
