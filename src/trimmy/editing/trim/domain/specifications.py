"""Specifications expressing trim range rules."""

from __future__ import annotations

from trimmy.editing.shared.domain.models import TrimRange
from trimmy.shared.compat import override
from trimmy.shared.domain.specification import Specification


class ValidTrimRangeSpecification(Specification[TrimRange]):
    """Satisfied when the range starts at or after zero and has length."""

    @override
    def is_satisfied_by(self, candidate: TrimRange) -> bool:
        """Return whether *candidate* is a well-formed trim range."""
        return candidate.start >= 0 and candidate.end > candidate.start
