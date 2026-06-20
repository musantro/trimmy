"""Render progress view showing global and per-platform rendering status."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qt_material_icons import MaterialIcon

from trimmy.app.components import (
    ActionButton,
    ActionButtonVariant,
    ProgressBar,
    RenderProgressItem,
    SectionLabel,
)
from trimmy.app.theme import Colors, Radii, Spacing, Typography
from trimmy.app.widgets import PreviewWidget


class RenderView(QWidget):
    """Full-page rendering progress view for a single platform at a time."""

    cancel_requested = Signal()
    done_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {Colors.SURFACE_DIM};")

        self._platform_items: dict[str, RenderProgressItem] = {}

        # Outer scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)  # ty: ignore[unresolved-attribute]
        scroll.setWidget(scroll_content)

        # Root layout for this widget
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        # Content card
        card = QWidget()
        card.setMaximumWidth(1000)
        card.setStyleSheet(
            f"QWidget#render-card {{"
            f" background: {Colors.SURFACE_CONTAINER_LOW};"
            f" border: 1px solid {Colors.OUTLINE_VARIANT};"
            f" border-radius: {Radii.XL}px;"
            f"}}",
        )
        card.setObjectName("render-card")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        card_layout.setSpacing(0)

        # Two-column layout inside card
        columns = QHBoxLayout()
        columns.setSpacing(Spacing.XL)
        card_layout.addLayout(columns)

        # ── LEFT COLUMN ──────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(Spacing.XL)

        # Global Progress section
        global_section = QVBoxLayout()
        global_section.setSpacing(Spacing.SM)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(0)

        global_label = SectionLabel("GLOBAL PROGRESS")
        header_row.addWidget(global_label)
        header_row.addStretch()

        pct_font = QFont(Typography.DISPLAY)
        pct_font.setPixelSize(Typography.HEADLINE_SIZE)
        pct_font.setWeight(QFont.Weight(Typography.HEADLINE_WEIGHT))

        self.global_pct_label = QLabel("0%")
        self.global_pct_label.setFont(pct_font)
        self.global_pct_label.setStyleSheet(
            f"color: {Colors.PRIMARY_CONTAINER}; background: transparent;",
        )
        header_row.addWidget(self.global_pct_label)

        global_section.addLayout(header_row)

        # Progress bar
        self.global_progress = ProgressBar(height=8)
        global_section.addWidget(self.global_progress)

        # Estimate row
        estimate_row = QHBoxLayout()
        estimate_row.setSpacing(Spacing.XS)

        estimate_icon_font = QFont()
        estimate_icon_font.setPixelSize(Typography.LABEL_SM_SIZE)

        timer_icon = MaterialIcon("timer")
        estimate_icon = QLabel()
        estimate_icon.setPixmap(
            timer_icon.pixmap(
                QSize(14, 14),
                color=QColor(Colors.ON_SURFACE_VARIANT),
            ),
        )
        estimate_icon.setStyleSheet("background: transparent;")
        estimate_row.addWidget(estimate_icon)

        estimate_font = QFont(Typography.MONO)
        estimate_font.setPixelSize(Typography.LABEL_SM_SIZE)
        estimate_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))

        self.estimate_label = QLabel("Estimated: --:-- remaining")
        self.estimate_label.setFont(estimate_font)
        self.estimate_label.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        estimate_row.addWidget(self.estimate_label)
        estimate_row.addStretch()

        global_section.addLayout(estimate_row)

        left.addLayout(global_section)

        # Platform progress section
        self._platform_layout = QVBoxLayout()
        self._platform_layout.setSpacing(Spacing.MD)
        left.addLayout(self._platform_layout)

        left.addStretch()

        # Cancel / Done button
        self.cancel_btn = ActionButton(
            "  CANCEL RENDER",
            ActionButtonVariant.DANGER,
            icon_name="cancel",
        )
        self.cancel_btn.clicked.connect(self._on_button_clicked)
        left.addWidget(self.cancel_btn)

        self._finished = False

        columns.addLayout(left, 1)

        # ── RIGHT COLUMN ─────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(0)

        self.preview = PreviewWidget()
        self.preview.setFixedSize(320, 569)
        self.preview.interactive = False

        right.addWidget(self.preview)
        right.addStretch()

        right_wrapper = QWidget()
        right_wrapper.setFixedWidth(320)
        right_wrapper.setStyleSheet("background: transparent;")
        right_wrapper.setLayout(right)

        columns.addWidget(right_wrapper, 0)

        scroll_layout.addWidget(card, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

    def set_global_progress(self, percent: int, estimate_text: str) -> None:
        """Update global progress bar, percentage label, and estimate text."""
        percent = max(0, min(100, percent))
        self.global_progress.set_value(percent)
        self.global_pct_label.setText(f"{percent}%")
        self.estimate_label.setText(estimate_text)

    def set_platform_info(self, name: str, percent: int) -> None:
        """Update or create a platform progress item by name."""
        percent = max(0, min(100, percent))
        if name in self._platform_items:
            self._platform_items[name].set_progress(percent)
        else:
            item = RenderProgressItem(name)
            item.set_progress(percent)
            self._platform_layout.addWidget(item)
            self._platform_items[name] = item

    def show_done(self) -> None:
        """Switch the cancel button to a 'Done' button after render completes."""
        self._finished = True
        self.cancel_btn.setText("  DONE")
        self.cancel_btn.setIcon(MaterialIcon("check_circle"))
        self.cancel_btn._apply_variant(ActionButtonVariant.PRIMARY)

    def _on_button_clicked(self) -> None:
        if self._finished:
            self.done_requested.emit()
        else:
            self.cancel_requested.emit()

    def reset(self) -> None:
        """Clear all progress state back to initial defaults."""
        self._finished = False
        self.cancel_btn.setText("  CANCEL RENDER")
        self.cancel_btn.setIcon(MaterialIcon("cancel"))
        self.cancel_btn._apply_variant(ActionButtonVariant.DANGER)

        self.global_progress.set_value(0)
        self.global_pct_label.setText("0%")
        self.estimate_label.setText("Estimated: --:-- remaining")

        for item in self._platform_items.values():
            self._platform_layout.removeWidget(item)
            item.deleteLater()
        self._platform_items.clear()

        self.preview.frame = None
        self.preview.update()
