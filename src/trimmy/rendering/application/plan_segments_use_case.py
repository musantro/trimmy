"""Use case that plans the segments a trim range will be rendered as."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.trim.domain import TrimRange
from trimmy.rendering.domain.models import Segment
from trimmy.rendering.domain.services import SegmentPlanner
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class PlanSegmentsRequest:
    """Request to split *trim_range* by *max_duration*."""

    trim_range: TrimRange
    max_duration: float | None


class PlanSegmentsUseCase(UseCase[PlanSegmentsRequest, list[Segment]]):
    """Plans the segments a trim range will be rendered as."""

    def __init__(self, planner: SegmentPlanner | None = None) -> None:
        self._planner = planner or SegmentPlanner()

    def plan(self, request: PlanSegmentsRequest) -> list[Segment]:
        """Return the planned segments for the request."""
        return self._planner.plan(request.trim_range, request.max_duration)
