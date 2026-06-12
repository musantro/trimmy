"""Tests for the preferences domain and application layers."""

from __future__ import annotations

from trimmy.preferences.application.use_cases import (
    LoadPreferencesUseCase,
    SavePreferencesUseCase,
)
from trimmy.preferences.domain.models import Preferences
from trimmy.preferences.domain.repositories import PreferencesRepository
from trimmy.shared.compat import override


class FakePreferencesRepository(PreferencesRepository):
    """In-memory preferences repository for tests."""

    def __init__(self, preferences: Preferences | None = None) -> None:
        self._preferences = preferences or Preferences.default()
        self.saved: Preferences | None = None

    @override
    def load(self) -> Preferences:
        return self._preferences

    @override
    def save(self, preferences: Preferences) -> None:
        self.saved = preferences


def test_preferences_default():
    prefs = Preferences.default()
    assert prefs.selected_platform == "instagram"
    assert prefs.selected_format == "feed"
    assert prefs.selected_quality == "max"
    assert prefs.split_ratio == 0.5
    assert prefs.volume == 50
    assert prefs.crops.top.is_empty
    assert prefs.crops.bottom.is_empty


def test_load_preferences_use_case():
    custom = Preferences.default()
    repo = FakePreferencesRepository(custom)
    assert LoadPreferencesUseCase(repo).execute() is custom


def test_save_preferences_use_case():
    repo = FakePreferencesRepository()
    prefs = Preferences.default()
    SavePreferencesUseCase(repo).execute(prefs)
    assert repo.saved is prefs
