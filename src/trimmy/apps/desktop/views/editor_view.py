"""Main editor view combining the source viewer and output preview panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from trimmy.apps.desktop.components import (
    ActionButton,
    ActionButtonVariant,
    PlatformSelector,
    PlaybackControls,
    VolumeControl,
)
from trimmy.apps.desktop.theme import Colors, Radii, Spacing, Typography
from trimmy.apps.desktop.widgets import (
    AudioLevelMeter,
    CropWidget,
    PreviewWidget,
    TimelineWidget,
)


class EditorView(QWidget):
    """Main editing interface with source viewer and output preview panel."""

    def __init__(self, crop_widget: CropWidget, parent: QWidget | None = None) -> None:
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
        self.crop_widget = crop_widget
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

        # Playback centered, volume right-aligned without overlapping hit areas.
        controls_container = QWidget()
        controls_container.setStyleSheet("background: transparent; border: none;")
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        edge_width = 180
        left_balance = QWidget()
        left_balance.setFixedWidth(edge_width)
        controls_layout.addWidget(left_balance)

        self.playback = PlaybackControls()
        controls_layout.addStretch()
        controls_layout.addWidget(self.playback)
        controls_layout.addStretch()

        right_slot = QWidget()
        right_slot.setFixedWidth(edge_width)
        right_layout_vol = QHBoxLayout(right_slot)
        right_layout_vol.setContentsMargins(0, 0, 0, 0)
        self.volume_control = VolumeControl()
        self.volume_control.setMaximumWidth(180)
        right_layout_vol.addWidget(
            self.volume_control,
            alignment=Qt.AlignRight,  # ty: ignore[unresolved-attribute]
        )
        controls_layout.addWidget(right_slot)

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

        self.flip_split_btn = ActionButton(
            "  FLIP TOP/BOTTOM",
            ActionButtonVariant.SECONDARY,
            icon_name="swap_vert",
        )
        self.flip_split_btn.setToolTip("Flip the top and bottom output areas")
        right_layout.addSpacing(Spacing.SECTION_GAP)
        right_layout.addWidget(self.flip_split_btn)

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

        self.send_queue_btn = ActionButton(
            "  SEND TO QUEUE",
            ActionButtonVariant.SECONDARY,
            icon_name="playlist_add",
        )
        bottom.addSpacing(Spacing.XS)
        bottom.addWidget(self.send_queue_btn)

        self.render_queue_btn = ActionButton(
            "  RENDER QUEUE",
            ActionButtonVariant.SECONDARY,
            icon_name="queue_play_next",
        )
        bottom.addSpacing(Spacing.XS)
        bottom.addWidget(self.render_queue_btn)

        self.queue_status = QLabel("QUEUE EMPTY")
        queue_status_font = QFont(Typography.MONO)
        queue_status_font.setPixelSize(Typography.LABEL_SM_SIZE)
        queue_status_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))
        self.queue_status.setFont(queue_status_font)
        self.queue_status.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        self.queue_status.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        bottom.addSpacing(Spacing.XS)
        bottom.addWidget(self.queue_status)

        self.stop_btn = ActionButton(
            "  CANCEL RENDER",
            ActionButtonVariant.DANGER,
            icon_name="cancel",
        )
        self.stop_btn.hide()
        bottom.addWidget(self.stop_btn)

        right_layout.addWidget(bottom_widget)

        root.addWidget(right, stretch=0)
