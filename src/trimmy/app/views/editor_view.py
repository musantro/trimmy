"""Main editor view combining the source viewer and output preview panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from trimmy.app.components import (
    ActionButton,
    ActionButtonVariant,
    PlatformSelector,
    PlaybackControls,
    VolumeControl,
)
from trimmy.app.theme import Colors, Radii, Spacing, Typography
from trimmy.app.widgets import (
    AudioLevelMeter,
    CropWidget,
    PreviewWidget,
    TimelineWidget,
)


class EditorView(QWidget):
    """Main editing interface with source viewer and output preview panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Left section ------------------------------------------------
        left = QWidget()
        left.setStyleSheet(
            f"background: {Colors.SURFACE_CONTAINER_LOWEST};"
            f" border-right: 1px solid {Colors.OUTLINE_VARIANT};",
        )

        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
        )
        left_layout.setSpacing(0)

        # Header row
        header_row = QHBoxLayout()
        header_label = QLabel("Source Viewer")
        header_font = QFont(Typography.HEADING)
        header_font.setPixelSize(20)
        header_font.setWeight(QFont.DemiBold)  # ty: ignore[unresolved-attribute]
        header_label.setFont(header_font)
        header_label.setStyleSheet(
            f"color: {Colors.ON_SURFACE}; background: transparent; border: none;",
        )
        header_row.addWidget(header_label)
        header_row.addStretch()
        left_layout.addLayout(header_row)

        # Crop widget
        self.crop_widget = CropWidget()
        left_layout.addWidget(self.crop_widget, stretch=1)

        # Timeline container
        timeline_container = QWidget()
        timeline_container.setStyleSheet(
            f"background: {Colors.SURFACE_CONTAINER_LOW};"
            f" border: 1px solid {Colors.OUTLINE_VARIANT};"
            f" border-radius: {Radii.DEFAULT}px;"
            f" padding: {Spacing.XS}px;",
        )
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(0)

        self.timeline = TimelineWidget()
        timeline_layout.addWidget(self.timeline)

        left_layout.addSpacing(Spacing.SECTION_GAP)
        left_layout.addWidget(timeline_container)

        self.audio_meter = AudioLevelMeter()
        self.audio_meter.configure(channels=0)
        left_layout.addSpacing(Spacing.SM)
        left_layout.addWidget(self.audio_meter)

        # Playback centered, volume right-aligned via stacked layers
        controls_container = QWidget()
        controls_container.setStyleSheet("background: transparent; border: none;")
        controls_stack = QStackedLayout(controls_container)
        controls_stack.setStackingMode(QStackedLayout.StackAll)  # ty: ignore[unresolved-attribute]
        controls_stack.setContentsMargins(0, 0, 0, 0)

        center_layer = QWidget()
        center_layer.setAttribute(
            Qt.WA_TransparentForMouseEvents,  # ty: ignore[unresolved-attribute]
            False,  # noqa: FBT003
        )
        center_layout = QHBoxLayout(center_layer)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.playback = PlaybackControls()
        center_layout.addStretch()
        center_layout.addWidget(self.playback)
        center_layout.addStretch()

        right_layer = QWidget()
        right_layer.setAttribute(
            Qt.WA_TransparentForMouseEvents,  # ty: ignore[unresolved-attribute]
            False,  # noqa: FBT003
        )
        right_layout_vol = QHBoxLayout(right_layer)
        right_layout_vol.setContentsMargins(0, 0, 0, 0)
        self.volume_control = VolumeControl()
        self.volume_control.setMaximumWidth(180)
        right_layout_vol.addStretch()
        right_layout_vol.addWidget(self.volume_control)

        controls_stack.addWidget(center_layer)
        controls_stack.addWidget(right_layer)

        left_layout.addSpacing(Spacing.SECTION_GAP)
        left_layout.addWidget(controls_container)

        root.addWidget(left, stretch=4)

        # -- Right section -----------------------------------------------
        right = QWidget()
        right.setFixedWidth(320)
        right.setStyleSheet(f"background: {Colors.SURFACE_CONTAINER_LOW};")

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
            Spacing.CONTAINER_PADDING,
        )
        right_layout.setSpacing(0)

        self.preview = PreviewWidget()
        right_layout.addWidget(self.preview, stretch=1)

        # -- Bottom: platform selection + render (fixed height) --
        bottom_widget = QWidget()
        bottom_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # ty: ignore[unresolved-attribute]
        bottom = QVBoxLayout(bottom_widget)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(0)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)  # ty: ignore[unresolved-attribute]
        separator.setStyleSheet(
            f"color: {Colors.OUTLINE_VARIANT}; background: transparent;",
        )
        bottom.addSpacing(Spacing.LG)
        bottom.addWidget(separator)
        bottom.addSpacing(Spacing.LG)

        platforms: list[tuple[str, str, list[tuple[str, str]]]] = [
            (
                "instagram",
                "IG",
                [("feed", "Feed"), ("reels", "Reels"), ("stories", "Stories")],
            ),
            ("tiktok", "TT", [("video", "Video")]),
            ("twitter", "X", [("post", "Post")]),
            ("whatsapp", "WA", [("chat", "Chat"), ("status", "Status")]),
            ("telegram", "TG", [("message", "Message")]),
        ]
        self.platform_selector = PlatformSelector(platforms)
        bottom.addWidget(self.platform_selector)

        bottom.addSpacing(Spacing.MD)

        self.render_btn = ActionButton(
            "  RENDER VIDEO",
            ActionButtonVariant.PRIMARY,
            icon_name="movie_filter",
        )
        bottom.addWidget(self.render_btn)

        self.stop_btn = ActionButton(
            "  CANCEL RENDER",
            ActionButtonVariant.DANGER,
            icon_name="cancel",
        )
        self.stop_btn.hide()
        bottom.addWidget(self.stop_btn)

        right_layout.addWidget(bottom_widget)

        root.addWidget(right, stretch=0)
