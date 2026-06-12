"""Specifications expressing trim range rules."""

from __future__ import annotations

from trimmy.shared.compat import override
from trimmy.shared.domain.specification import Specification
from trimmy.trim.domain.models import TrimRange


class ValidTrimRangeSpecification(Specification[TrimRange]):
    """Satisfied when the range starts at or after zero and has length."""

    @override
    def is_satisfied_by(self, candidate: TrimRange) -> bool:
        """Return whether *candidate* is a well-formed trim range."""
        return candidate.start >= 0 and candidate.end > candidate.start


class ExceedsMaxDurationSpecification(Specification[TrimRange]):
    """Satisfied when a range is longer than a platform's maximum."""

    def __init__(self, max_duration: float) -> None:
        self._max_duration = max_duration

    @override
    def is_satisfied_by(self, candidate: TrimRange) -> bool:
        """Return whether *candidate* exceeds the maximum duration."""
        return candidate.duration > self._max_duration
