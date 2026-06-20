"""Startup view showing the project creation screen with a drop zone."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from trimmy.app.components import DropZone
from trimmy.app.theme import Colors, Spacing, Typography


class StartupView(QWidget):
    """Full-screen startup view with centered heading, subtitle, and drop zone."""

    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {Colors.SURFACE_CONTAINER_LOWEST};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]

        container = QWidget()
        container.setMaximumWidth(768)
        container.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(Spacing.MARGIN_DESKTOP, 0, Spacing.MARGIN_DESKTOP, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]

        heading = QLabel("Start a new project")
        heading_font = QFont(Typography.DISPLAY)
        heading_font.setPixelSize(Typography.DISPLAY_SIZE)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        heading.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        heading.setStyleSheet(f"color: {Colors.ON_SURFACE}; background: transparent;")
        layout.addWidget(heading)

        layout.addSpacing(Spacing.XS)

        subtitle = QLabel("Drag and drop a video file to begin editing.")
        subtitle_font = QFont(Typography.BODY)
        subtitle_font.setPixelSize(Typography.BODY_LG_SIZE)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        subtitle.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        layout.addWidget(subtitle)

        layout.addSpacing(32)

        self._drop_zone = DropZone()
        self._drop_zone.open_clicked.connect(self.open_requested)
        layout.addWidget(self._drop_zone)

        outer.addWidget(container)
