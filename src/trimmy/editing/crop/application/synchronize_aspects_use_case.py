"""Use case that re-fits both crops to new aspect ratios."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.crop.domain.services import AspectRatioSynchronizer, CropAspects
from trimmy.editing.shared.domain.models import CropSelection, SourceSize
from trimmy.shared.domain.use_case import UseCase


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
