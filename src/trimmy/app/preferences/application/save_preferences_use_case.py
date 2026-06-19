"""Use case for saving user preferences."""

from __future__ import annotations

from trimmy.app.preferences.domain.models import Preferences
from trimmy.app.preferences.domain.preferences_repository import PreferencesRepository
from trimmy.shared.domain.use_case import UseCase


class SavePreferencesUseCase(UseCase[Preferences, None]):
    """Saves the user's preferences to the repository."""

    def __init__(self, repository: PreferencesRepository) -> None:
        self._repository = repository

    def save(self, request: Preferences) -> None:
        """Persist the given preferences."""
        self._repository.save(request)
