"""JSON-file implementation of the preferences repository."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from trimmy.app.preferences.domain.models import Preferences, TargetPreference
from trimmy.app.preferences.domain.preferences_repository import PreferencesRepository
from trimmy.editing.shared.domain.models import CropRect, CropSelection
from trimmy.shared.compat import override


def _default_config_path() -> Path:
    """Return the platform-appropriate path for the config file."""
    if sys.platform == "win32":
        base = Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local",
            ),
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"),
        )
    return base / "trimmy" / "config.json"


def _crop_to_dict(crop: CropRect) -> dict[str, float]:
    """Serialize a crop rectangle to a plain dict."""
    return {"x": crop.x, "y": crop.y, "w": crop.w, "h": crop.h}


def _crop_from_dict(data: dict[str, Any]) -> CropRect:
    """Deserialize a crop rectangle from a plain dict."""
    return CropRect(
        x=float(data.get("x", 0.0)),
        y=float(data.get("y", 0.0)),
        w=float(data.get("w", 0.0)),
        h=float(data.get("h", 0.0)),
    )


def _targets_from_list(
    data: object,
    fallback: TargetPreference,
) -> tuple[TargetPreference, ...]:
    """Deserialize selected targets, falling back to the legacy selection."""
    if not isinstance(data, list):
        return (fallback,)
    targets: list[TargetPreference] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        platform = item.get("platform")
        format_key = item.get("format_key")
        if isinstance(platform, str) and isinstance(format_key, str):
            targets.append(TargetPreference(platform, format_key))
    return tuple(targets)


class JsonPreferencesRepository(PreferencesRepository):
    """Persists preferences as a JSON file on disk."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_config_path()

    @override
    def load(self) -> Preferences:
        """Return preferences from disk, falling back to defaults."""
        defaults = Preferences.default()
        if not self._path.exists():
            return defaults
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return defaults

        selected_platform = data.get(
            "selected_platform",
            defaults.selected_platform,
        )
        selected_format = data.get(
            "selected_format",
            defaults.selected_format,
        )
        fallback_target = TargetPreference(selected_platform, selected_format)
        crops = data.get("crops", {})
        return Preferences(
            selected_platform=selected_platform,
            selected_format=selected_format,
            selected_quality=data.get(
                "selected_quality",
                defaults.selected_quality,
            ),
            split_ratio=data.get("split_ratio", defaults.split_ratio),
            volume=data.get("volume", defaults.volume),
            crops=CropSelection(
                top=_crop_from_dict(crops.get("top", {})),
                bottom=_crop_from_dict(crops.get("bottom", {})),
            ),
            selected_targets=_targets_from_list(
                data.get("selected_targets"),
                fallback_target,
            ),
        )

    @override
    def save(self, preferences: Preferences) -> None:
        """Write *preferences* to disk as JSON."""
        state = {
            "selected_platform": preferences.selected_platform,
            "selected_format": preferences.selected_format,
            "selected_quality": preferences.selected_quality,
            "split_ratio": preferences.split_ratio,
            "volume": preferences.volume,
            "selected_targets": [
                {
                    "platform": target.platform,
                    "format_key": target.format_key,
                }
                for target in preferences.selected_targets
            ],
            "crops": {
                "top": _crop_to_dict(preferences.crops.top),
                "bottom": _crop_to_dict(preferences.crops.bottom),
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
