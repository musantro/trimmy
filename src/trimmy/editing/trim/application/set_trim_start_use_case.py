"""Use case for adjusting the start of the trim range."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.trim.domain.models import TrimRange
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class SetTrimStartRequest:
    """Request to move the start of *current* to *value*."""

    current: TrimRange
    value: float


class SetTrimStartUseCase(UseCase[SetTrimStartRequest, TrimRange]):
    """Moves the trim start, keeping the range valid."""

    def set_start(self, request: SetTrimStartRequest) -> TrimRange:
        """Return the trim range with its start updated."""
        return request.current.with_start(request.value)
