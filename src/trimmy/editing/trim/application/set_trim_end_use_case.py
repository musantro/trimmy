"""Use case for adjusting the end of the trim range."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.trim.domain.models import TrimRange
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class SetTrimEndRequest:
    """Request to move the end of *current* to *value*."""

    current: TrimRange
    value: float
    total: float


class SetTrimEndUseCase(UseCase[SetTrimEndRequest, TrimRange]):
    """Moves the trim end, keeping the range valid."""

    def set_end(self, request: SetTrimEndRequest) -> TrimRange:
        """Return the trim range with its end updated."""
        return request.current.with_end(request.value, request.total)
