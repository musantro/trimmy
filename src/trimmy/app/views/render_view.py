"""Render progress view showing global and per-platform rendering status."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qt_material_icons import MaterialIcon

from trimmy.app.components import (
    ActionButton,
    ActionButtonVariant,
    AnimatedPercentageLabel,
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
    queue_job_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {Colors.SURFACE_DIM};")

        self._platform_items: dict[str, RenderProgressItem] = {}
        self._platform_order: tuple[str, ...] = ()
        self._queue_job_count = 0

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
        scroll_layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # ty: ignore[unresolved-attribute]
        scroll.setWidget(scroll_content)

        # Root layout for this widget
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        # Content card
        card = QWidget()
        card.setMinimumWidth(960)
        card.setMaximumWidth(1180)
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        card.setStyleSheet(
            f"QWidget#render-card {{"
            f" background: {Colors.SURFACE_CONTAINER_LOW};"
            f" border: 1px solid {Colors.OUTLINE_VARIANT};"
            f" border-radius: {Radii.XL}px;"
            f"}}",
        )
        card.setObjectName("render-card")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            Spacing.LG,
            Spacing.MD,
            Spacing.LG,
            Spacing.MD,
        )
        card_layout.setSpacing(0)

        # Two-column layout inside card
        columns = QHBoxLayout()
        columns.setSpacing(Spacing.LG)
        card_layout.addLayout(columns)

        # ── LEFT COLUMN ──────────────────────────────────────
        left_wrapper = QWidget()
        left_wrapper.setMinimumWidth(360)
        left_wrapper.setStyleSheet("background: transparent;")

        left = QVBoxLayout(left_wrapper)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(Spacing.LG)

        self._queue_section = QWidget()
        self._queue_section.setStyleSheet("background: transparent;")
        queue_layout = QVBoxLayout(self._queue_section)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.setSpacing(Spacing.SM)
        queue_layout.addWidget(SectionLabel("QUEUE JOBS"))

        self._queue_list = QListWidget()
        self._queue_list.setMinimumHeight(160)
        self._queue_list.setStyleSheet(
            f"QListWidget {{ background: {Colors.SURFACE_CONTAINER};"
            f" color: {Colors.ON_SURFACE};"
            f" border: 1px solid {Colors.OUTLINE_VARIANT};"
            f" border-radius: {Radii.DEFAULT}px; }}"
            f"QListWidget::item {{ padding: {Spacing.XS}px; }}"
            "QListWidget::item:selected {"
            f" background: {Colors.SURFACE_CONTAINER_HIGHEST};"
            " }"
        )
        self._queue_list.currentRowChanged.connect(self._on_queue_row_changed)
        queue_layout.addWidget(self._queue_list)
        self._queue_section.hide()
        left.addWidget(self._queue_section)

        # Global Progress section
        global_section = QVBoxLayout()
        global_section.setSpacing(Spacing.SM)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.MD)

        global_label = SectionLabel("GLOBAL PROGRESS")
        header_row.addWidget(global_label)
        header_row.addStretch()

        pct_font = QFont(Typography.DISPLAY)
        pct_font.setPixelSize(28)
        pct_font.setWeight(QFont.Weight(Typography.HEADLINE_WEIGHT))

        self.global_pct_label = AnimatedPercentageLabel()
        self.global_pct_label.setFont(pct_font)
        self.global_pct_label.setStyleSheet(
            f"color: {Colors.PRIMARY_CONTAINER}; background: transparent;",
        )
        header_row.addWidget(self.global_pct_label)

        global_section.addLayout(header_row)

        # Progress bar
        self.global_progress = ProgressBar(height=8)
        self.global_progress.value_changed.connect(
            self.global_pct_label.set_progress_value,
        )
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
        estimate_row.addStretch()
        estimate_row.addWidget(estimate_icon)

        estimate_font = QFont(Typography.MONO)
        estimate_font.setPixelSize(Typography.LABEL_SM_SIZE)
        estimate_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))

        self.estimate_label = QLabel("--:-- remaining")
        self.estimate_label.setFont(estimate_font)
        self.estimate_label.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        self.estimate_label.setAlignment(Qt.AlignRight)  # ty: ignore[unresolved-attribute]
        estimate_row.addWidget(self.estimate_label)

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
        self.cancel_btn.setMinimumWidth(220)
        self.cancel_btn.clicked.connect(self._on_button_clicked)
        left.addWidget(self.cancel_btn)

        self._finished = False

        columns.addWidget(left_wrapper, 1)

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
        self.estimate_label.setText(self._remaining_time_text(estimate_text))

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
            self._platform_order = (*self._platform_order, name)

    def set_platform_progress_items(
        self,
        items: tuple[tuple[str, int], ...],
    ) -> None:
        """Update per-target progress rows, rebuilding only when the row set changes."""
        labels = tuple(label for label, _percent in items)
        if labels != self._platform_order:
            self.clear_platform_info()
        for label, percent in items:
            self.set_platform_info(label, percent)

    def clear_platform_info(self) -> None:
        """Remove all per-target progress rows."""
        for item in self._platform_items.values():
            self._platform_layout.removeWidget(item)
            item.setParent(None)
            item.deleteLater()
        self._platform_items.clear()
        self._platform_order = ()

    def set_queue_jobs(self, labels: tuple[str, ...]) -> None:
        """Show queued trim jobs in the render screen sidebar."""
        self._queue_list.blockSignals(True)  # noqa: FBT003
        self._queue_list.clear()
        self._queue_job_count = len(labels)
        for label in labels:
            self._queue_list.addItem(QListWidgetItem(f"{label}\nQueued"))
        self._queue_section.setVisible(bool(labels))
        if labels:
            self._queue_list.setCurrentRow(0)
        self._queue_list.blockSignals(False)  # noqa: FBT003

    def set_queue_job_progress(self, index: int, percent: int, detail: str) -> None:
        """Update one queued trim job row."""
        if index < 0 or index >= self._queue_list.count():
            return
        percent = max(0, min(100, percent))
        item = self._queue_list.item(index)
        label = item.text().splitlines()[0]
        status = "Done" if percent >= 100 else f"{percent}%"
        if detail:
            status = f"{status} - {detail}"
        item.setText(f"{label}\n{status}")

    def select_queue_job(self, index: int) -> None:
        """Select a queued trim job without re-emitting selection changes."""
        if index < 0 or index >= self._queue_list.count():
            return
        self._queue_list.blockSignals(True)  # noqa: FBT003
        self._queue_list.setCurrentRow(index)
        self._queue_list.blockSignals(False)  # noqa: FBT003

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

        self.global_progress.set_value(0, animated=False)
        self.global_pct_label.set_progress_value(0)
        self.estimate_label.setText("--:-- remaining")

        self.clear_platform_info()
        self._queue_list.clear()
        self._queue_job_count = 0
        self._queue_section.hide()

        self.preview.frame = None
        self.preview.update()

    def _on_queue_row_changed(self, row: int) -> None:
        if 0 <= row < self._queue_job_count:
            self.queue_job_selected.emit(row)

    @staticmethod
    def _remaining_time_text(text: str) -> str:
        text = text.strip()
        for prefix in ("Rendering...", "Rendering…"):
            if text.startswith(prefix):
                text = text.removeprefix(prefix).strip()
        return text
