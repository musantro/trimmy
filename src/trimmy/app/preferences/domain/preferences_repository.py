"""Repository abstraction for persisting user preferences."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trimmy.app.preferences.domain.models import Preferences


class PreferencesRepository(ABC):
    """Loads and stores the user's preferences."""

    @abstractmethod
    def load(self) -> Preferences:
        """Return the stored preferences, or defaults when absent."""
        ...

    @abstractmethod
    def save(self, preferences: Preferences) -> None:
        """Persist *preferences*."""
        ...
