"""Specifications expressing encoding decisions."""

from __future__ import annotations

from trimmy.editing.shared.domain.models import TrimRange
from trimmy.rendering.domain.models import EncoderPreset
from trimmy.shared.compat import override
from trimmy.shared.domain.specification import Specification


class ExceedsMaxDurationSpecification(Specification[TrimRange]):
    """Satisfied when a range is longer than a platform's maximum."""

    def __init__(self, max_duration: float) -> None:
        self._max_duration = max_duration

    @override
    def is_satisfied_by(self, candidate: TrimRange) -> bool:
        """Return whether *candidate* exceeds the maximum duration."""
        return candidate.duration > self._max_duration


class FpsCapRequiredSpecification(Specification[float]):
    """Satisfied when a source frame rate exceeds the preset maximum."""

    def __init__(self, max_fps: int) -> None:
        self._max_fps = max_fps

    @override
    def is_satisfied_by(self, candidate: float) -> bool:
        """Return whether *candidate* fps must be capped."""
        return candidate > self._max_fps


class RequiresDynamicBitrateSpecification(Specification[EncoderPreset]):
    """Satisfied when a preset leaves the bitrate to be computed."""

    @override
    def is_satisfied_by(self, candidate: EncoderPreset) -> bool:
        """Return whether *candidate* needs a size-derived bitrate."""
        return candidate.maxrate is None
