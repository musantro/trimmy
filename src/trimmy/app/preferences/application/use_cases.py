"""Use cases for loading and saving user preferences."""

from __future__ import annotations

from trimmy.app.preferences.domain.models import Preferences
from trimmy.app.preferences.domain.preferences_repository import PreferencesRepository
from trimmy.shared.domain.use_case import UseCase


class LoadPreferencesUseCase(UseCase[None, Preferences]):
    """Loads the user's preferences from the repository."""

    def __init__(self, repository: PreferencesRepository) -> None:
        self._repository = repository

    def load(self) -> Preferences:
        """Return the loaded preferences."""
        return self._repository.load()


class SavePreferencesUseCase(UseCase[Preferences, None]):
    """Saves the user's preferences to the repository."""

    def __init__(self, repository: PreferencesRepository) -> None:
        self._repository = repository

    def save(self, request: Preferences) -> None:
        """Persist the given preferences."""
        self._repository.save(request)
