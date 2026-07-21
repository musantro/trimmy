"""In-memory implementation of the crop selection repository."""

from __future__ import annotations

from trimmy.editing.crop.domain.crop_selection_repository import CropSelectionRepository
from trimmy.editing.crop.domain.models import CropRect, CropSelection
from trimmy.shared.compat import override

_EMPTY_SELECTION = CropSelection(top=CropRect(), bottom=CropRect())


class InMemoryCropSelectionRepository(CropSelectionRepository):
    """Holds the crop selection in process memory for the running editor."""

    def __init__(self, selection: CropSelection = _EMPTY_SELECTION) -> None:
        self._selection = selection

    @override
    def get(self) -> CropSelection:
        """Return the in-memory crop selection."""
        return self._selection

    @override
    def save(self, selection: CropSelection) -> None:
        """Replace the in-memory crop selection with *selection*."""
        self._selection = selection
