"""Reusable PySide6 widget components styled with design tokens from DESIGN.md."""

from __future__ import annotations

import sys
from collections.abc import Sequence

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from trimmy.app.theme import Colors, Radii, Spacing, Typography


class SectionLabel(QLabel):
    """Uppercase section heading rendered in mono at label-sm size."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("section")


class ToggleButtonGroup(QWidget):
    """Mutually-exclusive group of checkable push buttons."""

    selection_changed = Signal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        selected: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._selected: str | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)

        for key, label in options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, k=key: self._on_clicked(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

        if selected is not None and selected in self._buttons:
            self.set_selected(selected)
        elif options:
            self.set_selected(options[0][0])

    def _on_clicked(self, key: str) -> None:
        if key == self._selected:
            self._buttons[key].setChecked(True)
            return
        self.set_selected(key)
        self.selection_changed.emit(key)

    def selected(self) -> str | None:
        """Return the key of the currently selected button."""
        return self._selected

    def set_selected(self, key: str) -> None:
        """Programmatically select the button identified by *key*."""
        self._selected = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)

    def button(self, key: str) -> QPushButton:
        """Return the underlying QPushButton for *key*."""
        return self._buttons[key]


class StatusLabel(QLabel):
    """Status feedback label with semantic colouring methods."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status")
        self.setWordWrap(True)

    def _apply(self, bg: str, fg: str, text: str) -> None:
        self.setStyleSheet(
            f"background: {bg}; color: {fg};"
            f" padding: {Spacing.XS}px {Spacing.SM // 4 * 3}px;"
            f" border-radius: {Radii.DEFAULT}px;"
            f" font-family: '{Typography.BODY}';"
            f" font-size: {Typography.BODY_MD_SIZE}px;"
        )
        self.setText(text)

    def set_error(self, text: str) -> None:
        """Display *text* with error styling."""
        self._apply(Colors.ERROR_STATUS_BG, Colors.ERROR_STATUS, text)

    def set_success(self, text: str) -> None:
        """Display *text* with success styling."""
        self._apply(Colors.SUCCESS_BG, Colors.SUCCESS, text)

    def set_warning(self, text: str) -> None:
        """Display *text* with warning styling."""
        self._apply(Colors.WARNING_BG, Colors.WARNING, text)

    def set_info(self, text: str) -> None:
        """Display *text* with informational styling."""
        self._apply(Colors.INFO_BG, Colors.INFO, text)

    @override
    def clear(self) -> None:
        """Remove all text and reset to default styling."""
        self.setStyleSheet("")
        self.setText("")


class VolumeControl(QWidget):
    """Mute button, horizontal slider, and percentage readout."""

    volume_changed = Signal(int)

    _ICON_ON = "\U0001f50a"
    _ICON_OFF = "\U0001f507"

    def __init__(
        self,
        initial_volume: int = 100,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._volume = max(0, min(100, initial_volume))
        self._muted = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)

        self._mute_btn = QPushButton(self._ICON_ON if self._volume else self._ICON_OFF)
        self._mute_btn.setFixedWidth(36)
        self._mute_btn.setStyleSheet(
            f"font-size: {Typography.BODY_MD_SIZE}px;"
            f" padding: {Spacing.BASE}px;"
            f" border-radius: {Radii.DEFAULT}px;"
        )
        self._mute_btn.clicked.connect(self.toggle_mute)
        layout.addWidget(self._mute_btn)

        self._slider = QSlider(Qt.Horizontal)  # ty: ignore[unresolved-attribute]
        self._slider.setRange(0, 100)
        self._slider.setValue(self._volume)
        self._slider.setFixedWidth(100)
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

        self._pct_label = QLabel(f"{self._volume}%")
        self._pct_label.setFixedWidth(36)
        self._pct_label.setObjectName("info")
        layout.addWidget(self._pct_label)

    def _on_slider(self, value: int) -> None:
        self._volume = value
        self._pct_label.setText(f"{value}%")
        self._mute_btn.setText(self._ICON_OFF if value == 0 else self._ICON_ON)
        self.volume_changed.emit(value)

    def toggle_mute(self) -> None:
        """Toggle the muted state and emit *volume_changed*."""
        self._muted = not self._muted
        self._slider.setEnabled(not self._muted)
        if self._muted:
            self._mute_btn.setText(self._ICON_OFF)
        else:
            self._mute_btn.setText(
                self._ICON_OFF if self._volume == 0 else self._ICON_ON,
            )
        self.volume_changed.emit(0 if self._muted else self._volume)

    def volume(self) -> int:
        """Return the effective volume (0 when muted)."""
        return 0 if self._muted else self._volume

    def is_muted(self) -> bool:
        """Return whether the control is currently muted."""
        return self._muted

    def set_volume(self, value: int) -> None:
        """Set the slider position to *value* (clamped 0-100)."""
        value = max(0, min(100, value))
        self._volume = value
        self._slider.setValue(value)


class KeybindingsDialog(QDialog):
    """Modal dialog listing keyboard shortcuts in a two-column layout."""

    def __init__(
        self,
        bindings: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedSize(360, 310)
        self.setStyleSheet(
            f"QDialog {{ background: {Colors.LEVEL_2}; }}"
            f"QLabel {{ color: {Colors.ON_SURFACE};"
            f" font-family: '{Typography.BODY}';"
            f" font-size: {Typography.BODY_MD_SIZE}px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.XS - 2)
        v_pad = Spacing.SM + 4
        layout.setContentsMargins(Spacing.MD, v_pad, Spacing.MD, v_pad)

        title = QLabel("Keyboard Shortcuts")
        title_font = QFont(Typography.HEADING)
        title_font.setPixelSize(Typography.BODY_LG_SIZE)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        layout.addWidget(title)
        layout.addSpacing(Spacing.XS)

        row_font = QFont(Typography.MONO)
        row_font.setPixelSize(Typography.LABEL_MD_SIZE)

        desc_font = QFont(Typography.BODY)
        desc_font.setPixelSize(Typography.LABEL_MD_SIZE)

        for key, desc in bindings:
            row = QHBoxLayout()
            key_label = QLabel(key)
            key_label.setFont(row_font)
            key_label.setFixedWidth(100)
            key_label.setStyleSheet(
                f"color: {Colors.PRIMARY}; font-weight: bold;"
            )
            desc_label = QLabel(desc)
            desc_label.setFont(desc_font)
            desc_label.setStyleSheet(f"color: {Colors.ON_SURFACE_VARIANT};")
            row.addWidget(key_label)
            row.addWidget(desc_label)
            layout.addLayout(row)

        layout.addSpacing(Spacing.XS + 2)
        hint = QLabel("Press Esc to close")
        hint.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        hint.setStyleSheet(
            f"color: {Colors.OUTLINE};"
            f" font-family: '{Typography.MONO}';"
            f" font-size: {Typography.LABEL_SM_SIZE}px;"
        )
        layout.addWidget(hint)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Close on Escape, delegate everything else."""
        if event.key() == Qt.Key_Escape:  # ty: ignore[unresolved-attribute]
            self.close()
        else:
            super().keyPressEvent(event)


class DropOverlay(QWidget):
    """Semi-transparent overlay shown while dragging a file onto the window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hide()
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False,  # noqa: FBT003
        )

    @override
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the drop-target border and label."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]

        overlay = QColor(Colors.LEVEL_0)
        overlay.setAlpha(220)
        p.fillRect(self.rect(), overlay)

        border = QColor(Colors.PRIMARY)
        pen = QPen(border, 3, Qt.DashLine)  # ty: ignore[unresolved-attribute]
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)  # ty: ignore[unresolved-attribute]
        margin = Spacing.LG
        p.drawRoundedRect(
            margin,
            margin,
            self.width() - 2 * margin,
            self.height() - 2 * margin,
            Radii.LG,
            Radii.LG,
        )

        p.setPen(QColor(Colors.PRIMARY))
        font = QFont(Typography.HEADING)
        font.setPixelSize(Typography.HEADLINE_SIZE)
        font.setBold(True)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "Drop video here")  # ty: ignore[unresolved-attribute]

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Forward resize to the base class."""
        super().resizeEvent(event)
