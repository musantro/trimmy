"""Use case that resets the crop selection to defaults for a new source."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.crop.domain.models import CropSelection, SourceSize
from trimmy.editing.crop.domain.services import DefaultCropFactory
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
