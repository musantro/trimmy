"""Use case that swaps the top and bottom output area properties."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.shared.domain.models import CropSelection
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class FlipOutputAreasRequest:
    """Request to exchange top and bottom output area properties."""

    split_ratio: float


@dataclass(frozen=True)
class FlipOutputAreasResult:
    """The updated output area properties after a flip."""

    selection: CropSelection
    split_ratio: float


class FlipOutputAreasUseCase(
    UseCase[FlipOutputAreasRequest, FlipOutputAreasResult],
):
    """Moves the current top area properties to bottom, and bottom to top."""

    def __init__(self, repository: CropSelectionRepository) -> None:
        self._repository = repository

    def flip(self, request: FlipOutputAreasRequest) -> FlipOutputAreasResult:
        """Swap crop assignments, invert the split ratio, persist and return them."""
        current = self._repository.get()
        selection = CropSelection(top=current.bottom, bottom=current.top)
        self._repository.save(selection)
        return FlipOutputAreasResult(
            selection=selection,
            split_ratio=1.0 - request.split_ratio,
        )
