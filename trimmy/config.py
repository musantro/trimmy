"""Persistent configuration for Trimmy user preferences."""

import json
import os
import sys
from pathlib import Path


def _config_dir() -> Path:
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
    return base / "trimmy"


CONFIG_PATH = _config_dir() / "config.json"

_DEFAULTS: dict = {
    "selected_platform": "instagram",
    "selected_format": "feed",
    "selected_quality": "max",
    "split_ratio": 0.5,
    "crops": {
        "top": {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
        "bottom": {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
    },
}


def load() -> dict:
    """Load config from disk, falling back to defaults."""
    if not CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
    else:
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged


def save(state: dict) -> None:
    """Write config state to disk as JSON."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
