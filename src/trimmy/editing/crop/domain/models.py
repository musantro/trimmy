"""
Crop value objects for the editing crop module.

These types are published by the crop module for consumers such as rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from trimmy.shared.compat import override
from trimmy.shared.domain.aggregate_root import AggregateRoot

MIN_TRIM_GAP = 0.1


class CropPosition(Enum):
    """Identifies one of the two stacked crop regions."""

    TOP = "top"
    BOTTOM = "bottom"


class CropHandle(Enum):
    """A corner handle used to resize a crop rectangle."""

    NW = "nw"
    NE = "ne"
    SW = "sw"
    SE = "se"

    @property
    def is_left(self) -> bool:
        """Return whether the handle is on the left edge."""
        return self in (CropHandle.NW, CropHandle.SW)

    @property
    def is_top(self) -> bool:
        """Return whether the handle is on the top edge."""
        return self in (CropHandle.NW, CropHandle.NE)


@dataclass(frozen=True)
class SourceSize:
    """Pixel dimensions of the source video frame."""

    width: int
    height: int


@dataclass(frozen=True)
class CropRect:
    """A crop region expressed in source-pixel coordinates."""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @property
    def right(self) -> float:
        """Return the x coordinate of the rectangle's right edge."""
        return self.x + self.w

    @property
    def bottom(self) -> float:
        """Return the y coordinate of the rectangle's bottom edge."""
        return self.y + self.h

    @property
    def is_empty(self) -> bool:
        """Return whether the rectangle has no positive area."""
        return self.w <= 0 or self.h <= 0


class CropSelection(AggregateRoot):
    """
    The pair of crop regions that compose the vertical output.

    The crops are exposed through read-only properties: the selection is
    effectively immutable like the other editing value objects, while the
    :class:`AggregateRoot` base lets it record domain events.
    """

    def __init__(self, top: CropRect, bottom: CropRect) -> None:
        super().__init__()
        self._top = top
        self._bottom = bottom

    @property
    def top(self) -> CropRect:
        """Return the top crop region."""
        return self._top

    @property
    def bottom(self) -> CropRect:
        """Return the bottom crop region."""
        return self._bottom

    def get(self, position: CropPosition) -> CropRect:
        """Return the crop rectangle for *position*."""
        return self._top if position is CropPosition.TOP else self._bottom

    def replace(self, position: CropPosition, rect: CropRect) -> CropSelection:
        """Return a copy with *position* set to *rect*."""
        if position is CropPosition.TOP:
            return CropSelection(top=rect, bottom=self._bottom)
        return CropSelection(top=self._top, bottom=rect)

    @override
    def __eq__(self, other: object) -> bool:
        """Return whether *other* holds the same top and bottom crops."""
        return (
            isinstance(other, CropSelection)
            and self._top == other._top
            and self._bottom == other._bottom
        )

    @override
    def __hash__(self) -> int:
        """Return a hash consistent with value equality."""
        return hash((self._top, self._bottom))
