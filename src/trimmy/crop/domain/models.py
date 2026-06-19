"""Value objects describing crop regions and the source frame."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


@dataclass(frozen=True)
class CropSelection:
    """The pair of crop regions that compose the vertical output."""

    top: CropRect
    bottom: CropRect

    def get(self, position: CropPosition) -> CropRect:
        """Return the crop rectangle for *position*."""
        return self.top if position is CropPosition.TOP else self.bottom

    def replace(self, position: CropPosition, rect: CropRect) -> CropSelection:
        """Return a copy with *position* set to *rect*."""
        if position is CropPosition.TOP:
            return CropSelection(top=rect, bottom=self.bottom)
        return CropSelection(top=self.top, bottom=rect)
