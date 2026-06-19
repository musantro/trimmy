"""Use case that translates one crop by a pixel delta."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.crop.domain.services import CropMover
from trimmy.editing.shared.domain.models import (
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
)
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class MoveCropRequest:
    """Request to translate one crop by a pixel delta."""

    position: CropPosition
    origin: CropRect
    dx: float
    dy: float
    source: SourceSize


class MoveCropUseCase(UseCase[MoveCropRequest, CropSelection]):
    """Moves a single crop and persists the updated selection."""

    def __init__(
        self,
        repository: CropSelectionRepository,
        mover: CropMover | None = None,
    ) -> None:
        self._repository = repository
        self._mover = mover or CropMover()

    def move(self, request: MoveCropRequest) -> CropSelection:
        """Move the requested crop, persist and return the selection."""
        moved = self._mover.move(
            request.origin,
            request.dx,
            request.dy,
            request.source,
        )
        selection = self._repository.get().replace(request.position, moved)
        self._repository.save(selection)
        return selection
