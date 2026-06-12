"""Use cases for adjusting the trim range and planning segments."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.shared.compat import override
from trimmy.shared.domain.use_case import UseCase
from trimmy.trim.domain.models import Segment, TrimRange
from trimmy.trim.domain.services import SegmentPlanner


@dataclass(frozen=True)
class SetTrimStartRequest:
    """Request to move the start of *current* to *value*."""

    current: TrimRange
    value: float


class SetTrimStartUseCase(UseCase[SetTrimStartRequest, TrimRange]):
    """Moves the trim start, keeping the range valid."""

    @override
    def execute(self, request: SetTrimStartRequest) -> TrimRange:
        """Return the trim range with its start updated."""
        return request.current.with_start(request.value)


@dataclass(frozen=True)
class SetTrimEndRequest:
    """Request to move the end of *current* to *value*."""

    current: TrimRange
    value: float
    total: float


class SetTrimEndUseCase(UseCase[SetTrimEndRequest, TrimRange]):
    """Moves the trim end, keeping the range valid."""

    @override
    def execute(self, request: SetTrimEndRequest) -> TrimRange:
        """Return the trim range with its end updated."""
        return request.current.with_end(request.value, request.total)


@dataclass(frozen=True)
class PlanSegmentsRequest:
    """Request to split *trim_range* by *max_duration*."""

    trim_range: TrimRange
    max_duration: float | None


class PlanSegmentsUseCase(UseCase[PlanSegmentsRequest, list[Segment]]):
    """Plans the segments a trim range will be rendered as."""

    def __init__(self, planner: SegmentPlanner | None = None) -> None:
        self._planner = planner or SegmentPlanner()

    @override
    def execute(self, request: PlanSegmentsRequest) -> list[Segment]:
        """Return the planned segments for the request."""
        return self._planner.plan(request.trim_range, request.max_duration)
