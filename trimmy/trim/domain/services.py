"""Domain service that splits a trim range into renderable segments."""

from __future__ import annotations

import math

from trimmy.trim.domain.models import Segment, TrimRange
from trimmy.trim.domain.specifications import ExceedsMaxDurationSpecification


class SegmentPlanner:
    """Splits a trim range into parts no longer than a maximum duration."""

    def plan(
        self,
        trim_range: TrimRange,
        max_duration: float | None,
    ) -> list[Segment]:
        """Return the ordered segments covering *trim_range*."""
        if max_duration is None or not ExceedsMaxDurationSpecification(
            max_duration,
        ).is_satisfied_by(trim_range):
            return [
                Segment(
                    index=1,
                    total=1,
                    start=trim_range.start,
                    end=trim_range.end,
                ),
            ]

        num_parts = math.ceil(trim_range.duration / max_duration)
        segments: list[Segment] = []
        for i in range(num_parts):
            seg_start = trim_range.start + i * max_duration
            seg_end = min(
                trim_range.start + (i + 1) * max_duration,
                trim_range.end,
            )
            segments.append(
                Segment(
                    index=i + 1,
                    total=num_parts,
                    start=seg_start,
                    end=seg_end,
                ),
            )
        return segments
