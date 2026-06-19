"""Repository abstraction for the active crop selection."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trimmy.crop.domain.models import CropSelection


class CropSelectionRepository(ABC):
    """Stores and retrieves the crop selection currently being edited."""

    @abstractmethod
    def get(self) -> CropSelection:
        """Return the currently stored crop selection."""
        ...

    @abstractmethod
    def save(self, selection: CropSelection) -> None:
        """Persist *selection* as the current crop selection."""
        ...
