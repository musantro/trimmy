"""Desktop composition root."""

from __future__ import annotations

import logging
import shutil
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from trimmy.apps.desktop.control_server import ControlServer
from trimmy.apps.desktop.main_window import DesktopDependencies, MainWindow
from trimmy.apps.desktop.theme import Typography, load_fonts
from trimmy.apps.desktop.widgets import CropWidget
from trimmy.editing.crop.domain.services import AspectRatioCalculator
from trimmy.editing.crop.infrastructure.in_memory_crop_selection_repository import (
    InMemoryCropSelectionRepository,
)
from trimmy.preferences.infrastructure.json_preferences_repository import (
    JsonPreferencesRepository,
)
from trimmy.rendering.application.probe_video_use_case import ProbeVideoUseCase
from trimmy.rendering.domain.services import FormatSelector
from trimmy.rendering.infrastructure.ffmpeg import (
    FFmpegRenderingBackend,
    FFprobeVideoProber,
)
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus
from trimmy.shared.infrastructure.pyside_event_bus import PySideEventBus

logger = logging.getLogger(__name__)


def run(file_path: str | None = None) -> None:
    """Compose and launch the PySide desktop application."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        logger.error("ffmpeg and ffprobe must be installed and in PATH.")
        raise SystemExit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    load_fonts()
    default_font = QFont(Typography.BODY)
    default_font.setPixelSize(Typography.BODY_MD_SIZE)
    default_font.setWeight(QFont.Weight(Typography.BODY_WEIGHT))
    app.setFont(default_font)

    dependencies = DesktopDependencies(
        presets=InMemoryPresetRepository(),
        format_selector=FormatSelector(),
        aspect_calculator=AspectRatioCalculator(),
        probe=ProbeVideoUseCase(FFprobeVideoProber()),
        preferences_repository=JsonPreferencesRepository(),
        event_bus=PySideEventBus(),
        rendering_backend_factory=FFmpegRenderingBackend,
        crop_widget=CropWidget(InMemoryCropSelectionRepository()),
        local_event_bus_factory=InMemoryEventBus,
    )
    window = MainWindow(dependencies, file_path)
    window._control_server = ControlServer(window)  # ty: ignore[unresolved-attribute]
    window.show()
    raise SystemExit(app.exec())
