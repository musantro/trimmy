"""Pure domain services that compute crop geometry."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.models import (
    CropHandle,
    CropRect,
    CropSelection,
    SourceSize,
)

MIN_CROP_SIZE = 30.0


@dataclass(frozen=True)
class CropAspects:
    """The aspect ratios required for the top and bottom crops."""

    top: float
    bottom: float


class DefaultCropFactory:
    """Builds the initial crop selection for a freshly opened video."""

    def create(self, source: SourceSize) -> CropSelection:
        """Return a sensible default crop selection for *source*."""
        w = source.width * 0.6
        h = source.height * 0.45
        return CropSelection(
            top=CropRect(0.0, 0.0, w, h),
            bottom=CropRect(source.width * 0.2, source.height * 0.5, w, h),
        )


class AspectRatioCalculator:
    """Derives crop aspect ratios from the output frame and split ratio."""

    def calculate(
        self,
        output_width: int,
        output_height: int,
        split_ratio: float,
    ) -> CropAspects:
        """Return the aspect ratios for the given split of the output frame."""
        top_h = output_height * split_ratio
        bottom_h = output_height * (1 - split_ratio)
        return CropAspects(
            top=output_width / top_h,
            bottom=output_width / bottom_h,
        )


class AspectRatioSynchronizer:
    """Resizes a crop so it matches an aspect ratio without leaving bounds."""

    def synchronize(
        self,
        crop: CropRect,
        aspect: float,
        source: SourceSize,
    ) -> CropRect:
        """Return *crop* resized to *aspect* and clamped inside *source*."""
        clamped_h = min(crop.w / aspect, source.height)
        w = min(clamped_h * aspect, source.width)
        h = clamped_h
        x = crop.x
        y = crop.y
        if x + w > source.width:
            x = source.width - w
        if y + h > source.height:
            y = source.height - h
        return CropRect(max(0.0, x), max(0.0, y), w, h)


class CropMover:
    """Translates a crop by a delta, clamped to the source frame."""

    def move(
        self,
        origin: CropRect,
        dx: float,
        dy: float,
        source: SourceSize,
    ) -> CropRect:
        """Return *origin* shifted by ``(dx, dy)`` and clamped in bounds."""
        x = max(0.0, min(origin.x + dx, source.width - origin.w))
        y = max(0.0, min(origin.y + dy, source.height - origin.h))
        return CropRect(x, y, origin.w, origin.h)


class CropResizer:
    """Resizes a crop from a corner handle while preserving its aspect."""

    def resize(
        self,
        origin: CropRect,
        handle: CropHandle,
        dx: float,
        aspect: float,
        source: SourceSize,
    ) -> CropRect:
        """Return *origin* resized from *handle* by *dx*, keeping *aspect*."""
        w = origin.w - dx if handle.is_left else origin.w + dx
        w = max(MIN_CROP_SIZE, w)
        h = w / aspect

        x = origin.right - w if handle.is_left else origin.x
        y = origin.bottom - h if handle.is_top else origin.y
        x = max(0.0, x)
        y = max(0.0, y)

        if x + w > source.width:
            w = source.width - x
            h = w / aspect
        if y + h > source.height:
            h = source.height - y
            w = h * aspect
        return CropRect(x, y, w, h)
