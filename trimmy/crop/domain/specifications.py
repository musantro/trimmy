"""Specifications expressing crop validity rules."""

from __future__ import annotations

from trimmy.crop.domain.models import CropRect, SourceSize
from trimmy.shared.compat import override
from trimmy.shared.domain.specification import Specification


class NonEmptyCropSpecification(Specification[CropRect]):
    """Satisfied when the crop has positive width and height."""

    @override
    def is_satisfied_by(self, candidate: CropRect) -> bool:
        """Return whether *candidate* covers a positive area."""
        return not candidate.is_empty


class WithinSourceBoundsSpecification(Specification[CropRect]):
    """Satisfied when the crop lies entirely inside the source frame."""

    def __init__(self, source: SourceSize) -> None:
        self._source = source

    @override
    def is_satisfied_by(self, candidate: CropRect) -> bool:
        """Return whether *candidate* fits within the source bounds."""
        return (
            candidate.x >= 0
            and candidate.y >= 0
            and candidate.right <= self._source.width
            and candidate.bottom <= self._source.height
        )


def usable_crop_specification(source: SourceSize) -> Specification[CropRect]:
    """Build the rule for a crop that is both non-empty and in bounds."""
    return NonEmptyCropSpecification() & WithinSourceBoundsSpecification(source)
