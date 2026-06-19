"""Use cases that mutate the crop selection through the repository."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.crop.domain.models import (
    CropHandle,
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
)
from trimmy.crop.domain.services import (
    AspectRatioSynchronizer,
    CropAspects,
    CropMover,
    CropResizer,
    DefaultCropFactory,
)
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class InitializeCropsRequest:
    """Request to reset crops to their defaults for a new source."""

    source: SourceSize


class InitializeCropsUseCase(UseCase[InitializeCropsRequest, CropSelection]):
    """Resets the crop selection to defaults for the opened video."""

    def __init__(
        self,
        repository: CropSelectionRepository,
        factory: DefaultCropFactory | None = None,
    ) -> None:
        self._repository = repository
        self._factory = factory or DefaultCropFactory()

    def initialize(self, request: InitializeCropsRequest) -> CropSelection:
        """Create, persist and return the default crop selection."""
        selection = self._factory.create(request.source)
        self._repository.save(selection)
        return selection


@dataclass(frozen=True)
class SynchronizeAspectsRequest:
    """Request to re-fit both crops to new aspect ratios."""

    aspects: CropAspects
    source: SourceSize


class SynchronizeAspectsUseCase(
    UseCase[SynchronizeAspectsRequest, CropSelection],
):
    """Re-shapes both crops so they match the required aspect ratios."""

    def __init__(
        self,
        repository: CropSelectionRepository,
        synchronizer: AspectRatioSynchronizer | None = None,
    ) -> None:
        self._repository = repository
        self._synchronizer = synchronizer or AspectRatioSynchronizer()

    def synchronize(self, request: SynchronizeAspectsRequest) -> CropSelection:
        """Synchronize both crops, persist and return the new selection."""
        current = self._repository.get()
        selection = CropSelection(
            top=self._synchronizer.synchronize(
                current.top,
                request.aspects.top,
                request.source,
            ),
            bottom=self._synchronizer.synchronize(
                current.bottom,
                request.aspects.bottom,
                request.source,
            ),
        )
        self._repository.save(selection)
        return selection


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
