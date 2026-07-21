"""Use case that resizes one crop from a corner handle."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.crop.domain.models import (
    CropHandle,
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
)
from trimmy.editing.crop.domain.services import CropResizer
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class ResizeCropRequest:
    """Request to resize one crop from a corner handle."""

    position: CropPosition
    handle: CropHandle
    origin: CropRect
    dx: float
    aspect: float
    source: SourceSize


class ResizeCropUseCase(UseCase[ResizeCropRequest, CropSelection]):
    """Resizes a single crop from a handle, preserving its aspect ratio."""

    def __init__(
        self,
        repository: CropSelectionRepository,
        resizer: CropResizer | None = None,
    ) -> None:
        self._repository = repository
        self._resizer = resizer or CropResizer()

    def resize(self, request: ResizeCropRequest) -> CropSelection:
        """Resize the requested crop, persist and return the selection."""
        resized = self._resizer.resize(
            request.origin,
            request.handle,
            request.dx,
            request.aspect,
            request.source,
        )
        selection = self._repository.get().replace(request.position, resized)
        self._repository.save(selection)
        return selection
