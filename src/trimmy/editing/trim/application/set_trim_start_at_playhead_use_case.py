"""Use case for setting trim start from the current playhead."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.trim.domain.models import TrimRange
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class SetTrimStartAtPlayheadRequest:
    """Request to set *current* start to the playhead *value*."""

    current: TrimRange
    value: float
    total: float


class SetTrimStartAtPlayheadUseCase(
    UseCase[SetTrimStartAtPlayheadRequest, TrimRange],
):
    """Sets trim start from the playhead, preserving keyboard workflow intent."""

    def set_start(self, request: SetTrimStartAtPlayheadRequest) -> TrimRange:
        """Return the trim range with start moved to the playhead."""
        value = min(request.total, max(0.0, request.value))
        if value > request.current.end:
            return TrimRange(value, value)
        return request.current.with_start(value)
