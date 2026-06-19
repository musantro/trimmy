"""Repository abstraction for the platform/quality preset catalogue."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trimmy.rendering.domain.models import (
    EncoderPreset,
    PlatformDisplayInfo,
    PlatformFormat,
)


class PresetRepository(ABC):
    """Provides encoder presets, display info and formats per platform."""

    @abstractmethod
    def encoder_preset(self, platform: str, quality: str) -> EncoderPreset:
        """Return the encoder preset for *platform* and *quality*."""
        ...

    @abstractmethod
    def display_info(self, platform: str, quality: str) -> PlatformDisplayInfo:
        """Return the human-readable info for *platform* and *quality*."""
        ...

    @abstractmethod
    def formats(self, platform: str) -> tuple[PlatformFormat, ...]:
        """Return the available upload formats for *platform*."""
        ...
