"""Reusable PySide6 widget components styled with design tokens from DESIGN.md."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from enum import Enum

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
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

from trimmy.app.icons import MaterialIcon
from trimmy.app.theme import Colors, Radii, Spacing, Typography


class ActionButtonVariant(Enum):
    """Visual variants for ActionButton."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"


_ACTION_STYLES: dict[ActionButtonVariant, dict[str, str | int]] = {
    ActionButtonVariant.PRIMARY: {
        "bg": Colors.PRIMARY_CONTAINER,
        "bg_hover": Colors.PRIMARY_DIM,
        "fg": Colors.ON_PRIMARY_CONTAINER,
        "border": "none",
        "font_size": Typography.LABEL_MD_SIZE,
        "font_weight": Typography.LABEL_MD_WEIGHT,
        "radius": Radii.DEFAULT,
        "padding_v": Spacing.SM,
        "padding_h": Spacing.SM,
    },
    ActionButtonVariant.SECONDARY: {
        "bg": Colors.SECONDARY_CONTAINER,
        "bg_hover": Colors.SECONDARY_FIXED,
        "fg": Colors.ON_SECONDARY_CONTAINER,
        "border": "none",
        "font_size": Typography.LABEL_MD_SIZE,
        "font_weight": Typography.LABEL_MD_WEIGHT,
        "radius": Radii.DEFAULT,
        "padding_v": Spacing.XS,
        "padding_h": Spacing.SM + Spacing.XS,
    },
    ActionButtonVariant.DANGER: {
        "bg": "transparent",
        "bg_hover": Colors.ERROR_CONTAINER,
        "fg": Colors.ERROR,
        "border": f"1px solid {Colors.ERROR}",
        "font_size": Typography.LABEL_SM_SIZE,
        "font_weight": Typography.LABEL_SM_WEIGHT,
        "radius": Radii.LG,
        "padding_v": Spacing.SM,
        "padding_h": Spacing.SM,
    },
}


class ActionButton(QPushButton):
    """Styled push button with icon and variant-based theming."""

    def __init__(
        self,
        text: str,
        variant: ActionButtonVariant = ActionButtonVariant.PRIMARY,
        icon_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if icon_name is not None:
            self.setIcon(MaterialIcon(icon_name))
            self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._apply_variant(variant)

    def _apply_variant(self, variant: ActionButtonVariant) -> None:
        s = _ACTION_STYLES[variant]
        self.setStyleSheet(
            f"QPushButton {{"
            f" background-color: {s['bg']};"
            f" color: {s['fg']};"
            f" border: {s['border']};"
            f" border-radius: {s['radius']}px;"
            f" font-family: '{Typography.MONO}';"
            f" font-size: {s['font_size']}px;"
            f" font-weight: {s['font_weight']};"
            f" padding: {s['padding_v']}px {s['padding_h']}px;"
            f"}}"
            f"QPushButton:hover {{"
            f" background-color: {s['bg_hover']};"
            f"}}"
            f"QPushButton:disabled {{"
            f" background-color: {Colors.SURFACE_CONTAINER_HIGH};"
            f" color: {Colors.OUTLINE};"
            f" border: none;"
            f"}}",
        )


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


class VolumeControl(QWidget):
    """Mute button, horizontal slider, and percentage readout."""

    volume_changed = Signal(int)

    _ICON_ON = "volume_up"
    _ICON_OFF = "volume_off"

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

        self._mute_btn = QPushButton()
        self._mute_btn.setIcon(
            MaterialIcon(self._ICON_ON if self._volume else self._ICON_OFF),
        )
        self._mute_btn.setIconSize(QSize(20, 20))
        self._mute_btn.setFixedWidth(36)
        self._mute_btn.setStyleSheet(
            f"padding: {Spacing.BASE}px; border-radius: {Radii.DEFAULT}px;",
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
        self._mute_btn.setIcon(
            MaterialIcon(self._ICON_OFF if value == 0 else self._ICON_ON),
        )
        self.volume_changed.emit(value)

    def toggle_mute(self) -> None:
        """Toggle the muted state and emit *volume_changed*."""
        self._muted = not self._muted
        self._slider.setEnabled(not self._muted)
        if self._muted:
            self._mute_btn.setIcon(MaterialIcon(self._ICON_OFF))
        else:
            self._mute_btn.setIcon(
                MaterialIcon(
                    self._ICON_OFF if self._volume == 0 else self._ICON_ON,
                ),
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
            f" font-size: {Typography.BODY_MD_SIZE}px; }}",
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
            key_label.setStyleSheet(f"color: {Colors.PRIMARY}; font-weight: bold;")
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
            f" font-size: {Typography.LABEL_SM_SIZE}px;",
        )
        layout.addWidget(hint)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
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
    def paintEvent(self, event: QPaintEvent) -> None:
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
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Forward resize to the base class."""
        super().resizeEvent(event)


# ---------------------------------------------------------------------------
# New components
# ---------------------------------------------------------------------------


class TopNavBar(QWidget):
    """Fixed-height top navigation bar with brand and action buttons."""

    settings_clicked = Signal()
    help_clicked = Signal()

    def __init__(
        self,
        version_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("topnav")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            Spacing.CONTAINER_PADDING,
            0,
            Spacing.CONTAINER_PADDING,
            0,
        )
        layout.setSpacing(0)

        brand_font = QFont(Typography.HEADING)
        brand_font.setPixelSize(24)
        brand_font.setBold(True)

        self._brand = QLabel("Trimmy")
        self._brand.setFont(brand_font)
        self._brand.setStyleSheet(
            f"color: {Colors.PRIMARY_CONTAINER}; background: transparent;",
        )
        layout.addWidget(self._brand)

        version_font = QFont(Typography.MONO)
        version_font.setPixelSize(10)

        self._version = QLabel(version_text)
        self._version.setFont(version_font)
        self._version.setStyleSheet(
            f"color: {Colors.OUTLINE}; background: transparent;"
            f" margin-left: {Spacing.XS}px; margin-bottom: 2px;",
        )
        self._version.setAlignment(Qt.AlignBottom)  # ty: ignore[unresolved-attribute]
        layout.addWidget(self._version)

        layout.addStretch()

        btn_ss = (
            f"QPushButton {{ background: transparent;"
            f" color: {Colors.ON_SURFACE_VARIANT};"
            f" border: none; border-radius: {Radii.DEFAULT}px;"
            f" font-size: 16px; }}"
            f"QPushButton:hover {{ background: {Colors.SURFACE_CONTAINER_HIGH};"
            f" color: {Colors.ON_SURFACE}; }}"
        )

        self._settings_btn = QPushButton()
        self._settings_btn.setIcon(MaterialIcon("settings"))
        self._settings_btn.setIconSize(QSize(18, 18))
        self._settings_btn.setFixedSize(32, 32)
        self._settings_btn.setStyleSheet(btn_ss)
        self._settings_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._settings_btn.clicked.connect(self.settings_clicked)
        layout.addWidget(self._settings_btn)

        self._help_btn = QPushButton()
        self._help_btn.setIcon(MaterialIcon("help"))
        self._help_btn.setIconSize(QSize(18, 18))
        self._help_btn.setFixedSize(32, 32)
        self._help_btn.setStyleSheet(btn_ss)
        self._help_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._help_btn.clicked.connect(self.help_clicked)
        layout.addWidget(self._help_btn)

    def set_version(self, text: str) -> None:
        """Update the version label text."""
        self._version.setText(text)


class SidebarNavButton(QWidget):
    """Single sidebar navigation button with icon and label."""

    clicked = Signal()

    _BG_ACTIVE = QColor(Colors.SECONDARY_CONTAINER)
    _BG_HOVER = QColor(Colors.SURFACE_CONTAINER_HIGHEST)
    _FG_ACTIVE = Colors.ON_SECONDARY_CONTAINER
    _FG_NORMAL = Colors.ON_SURFACE_VARIANT

    def __init__(
        self,
        icon_name: str,
        label_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active = False
        self._hovered = False
        self._icon_name = icon_name
        self._bg = QColor(0, 0, 0, 0)
        self.setFixedSize(72, 64)
        self.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        layout.addWidget(self._icon_label, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

        self._text_label = QLabel(label_text)
        text_font = QFont(Typography.MONO)
        text_font.setPixelSize(Typography.LABEL_SM_SIZE)
        text_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))
        self._text_label.setFont(text_font)
        self._text_label.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        layout.addWidget(self._text_label, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

        self._apply_state()

    def _apply_state(self) -> None:
        if self._active:
            self._bg = self._BG_ACTIVE
            fg = self._FG_ACTIVE
        elif self._hovered:
            self._bg = self._BG_HOVER
            fg = self._FG_NORMAL
        else:
            self._bg = QColor(0, 0, 0, 0)
            fg = self._FG_NORMAL

        self._icon_label.setPixmap(
            MaterialIcon(self._icon_name).colored_pixmap(QSize(20, 20), QColor(fg)),
        )
        self._text_label.setStyleSheet(f"color: {fg}; background: transparent;")
        self.update()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the rounded background."""
        if self._bg.alpha() > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
            p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
            p.setBrush(self._bg)
            p.drawRoundedRect(self.rect(), Radii.LG, Radii.LG)
            p.end()

    @property
    def active(self) -> bool:
        """Whether this button is in the active state."""
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        self._apply_state()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit clicked on left button press."""
        if event.button() == Qt.LeftButton:  # ty: ignore[unresolved-attribute]
            self.clicked.emit()
        super().mousePressEvent(event)

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        """Apply hover style."""
        self._hovered = True
        self._apply_state()
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        """Remove hover style."""
        self._hovered = False
        self._apply_state()
        super().leaveEvent(event)


class SidebarNavigation(QWidget):
    """Vertical sidebar with navigation buttons and shortcuts link."""

    nav_changed = Signal(str)
    shortcuts_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, Spacing.XS, 4, Spacing.XS)
        layout.setSpacing(Spacing.COMPONENT_GAP)

        self._buttons: dict[str, SidebarNavButton] = {}

        nav_items: list[tuple[str, str, str]] = [
            ("folder_open", "Open", "open"),
            ("movie_edit", "Edit", "edit"),
            ("send", "Render", "render"),
        ]

        for icon, label, key in nav_items:
            btn = SidebarNavButton(icon, label)
            btn.clicked.connect(lambda k=key: self._on_button_clicked(k))
            layout.addWidget(btn, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]
            self._buttons[key] = btn

        layout.addStretch()

        self._shortcuts_btn = QPushButton("Shortcuts")
        self._shortcuts_btn.setStyleSheet(
            f"QPushButton {{ background: transparent;"
            f" color: {Colors.ON_SURFACE_VARIANT};"
            f" border: none; font-family: '{Typography.MONO}';"
            f" font-size: {Typography.LABEL_SM_SIZE}px;"
            f" padding: {Spacing.BASE}px; }}"
            f"QPushButton:hover {{ color: {Colors.PRIMARY_CONTAINER}; }}",
        )
        self._shortcuts_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._shortcuts_btn.clicked.connect(self.shortcuts_requested)
        layout.addWidget(self._shortcuts_btn)

    def _on_button_clicked(self, key: str) -> None:
        self.set_active(key)
        self.nav_changed.emit(key)

    def set_active(self, name: str) -> None:
        """Toggle the active state to the button identified by *name*."""
        for key, btn in self._buttons.items():
            btn.active = key == name


class DropZone(QWidget):
    """Drag-and-drop zone with open-video button for the startup screen."""

    open_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 280)
        self._hovered = False

        self._update_border_style()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        outer.setSpacing(Spacing.SM)
        outer.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]

        upload_icon = MaterialIcon("upload")
        icon_label = QLabel()
        icon_label.setPixmap(
            upload_icon.colored_pixmap(
                QSize(40, 40), QColor(Colors.ON_SURFACE_VARIANT)
            ),
        )
        icon_label.setFixedSize(80, 80)
        icon_label.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        icon_label.setStyleSheet(
            f"background: {Colors.SURFACE_CONTAINER_HIGHEST}; border-radius: 40px;",
        )
        outer.addWidget(icon_label, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

        title = QLabel("Drag & Drop Video File")
        title_font = QFont(Typography.HEADING)
        title_font.setPixelSize(Typography.HEADLINE_MOBILE_SIZE)
        title_font.setWeight(QFont.Weight(Typography.HEADLINE_WEIGHT))
        title.setFont(title_font)
        title.setStyleSheet(f"color: {Colors.ON_SURFACE}; background: transparent;")
        title.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        outer.addWidget(title)

        divider = QLabel("— OR —")
        divider_font = QFont(Typography.MONO)
        divider_font.setPixelSize(Typography.LABEL_SM_SIZE)
        divider_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))
        divider.setFont(divider_font)
        divider.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        divider.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        outer.addWidget(divider)

        open_btn = ActionButton(
            "  Open Video",
            ActionButtonVariant.SECONDARY,
            icon_name="folder_open",
        )
        open_btn.clicked.connect(self.open_clicked)
        outer.addWidget(open_btn, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

        formats = QLabel("SUPPORTED FORMATS: MP4, MOV, AVI (UP TO 4K)")
        formats_font = QFont(Typography.MONO)
        formats_font.setPixelSize(Typography.LABEL_MD_SIZE)
        formats_font.setWeight(QFont.Weight(Typography.LABEL_MD_WEIGHT))
        formats.setFont(formats_font)
        formats.setStyleSheet(
            f"color: {Colors.ON_SURFACE_VARIANT}; background: transparent;",
        )
        formats.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        outer.addWidget(formats)

    def _update_border_style(self) -> None:
        border_color = Colors.OUTLINE if self._hovered else Colors.SURFACE_VARIANT
        self.setStyleSheet(
            f"DropZone {{ background: {Colors.SURFACE_CONTAINER};"
            f" border: 2px dashed {border_color};"
            f" border-radius: {Radii.XL}px; }}",
        )

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        """Highlight border on hover."""
        self._hovered = True
        self._update_border_style()
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        """Reset border on leave."""
        self._hovered = False
        self._update_border_style()
        super().leaveEvent(event)


class PlatformSelector(QWidget):
    """Platform and format selector grid."""

    platform_changed = Signal(str)
    format_changed = Signal(str, str)

    def __init__(
        self,
        platforms: Sequence[tuple[str, str, Sequence[tuple[str, str]]]],
        selected_platform: str = "",
        selected_format: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._platforms = list(platforms)
        self._selected_platform = ""
        self._selected_format = ""
        self._format_rows: dict[str, QWidget] = {}
        self._format_buttons: dict[str, dict[str, QPushButton]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)

        layout.addWidget(SectionLabel("PLATFORM SELECTION"))

        for plat_key, _plat_label, formats in self._platforms:
            if len(formats) < 1:
                continue
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(
                Spacing.XS,
                Spacing.XS,
                Spacing.XS,
                Spacing.XS,
            )
            row_layout.setSpacing(Spacing.BASE)

            row.setStyleSheet(
                f"background: rgba(51, 53, 57, 0.5);"
                f" border: 1px solid {Colors.OUTLINE_VARIANT};"
                f" border-radius: {Radii.DEFAULT}px;",
            )

            lbl = QLabel(plat_key.upper())
            lbl_font = QFont(Typography.MONO)
            lbl_font.setPixelSize(10)
            lbl.setFont(lbl_font)
            lbl.setStyleSheet(
                f"color: {Colors.ON_SURFACE_VARIANT};"
                f" background: transparent; border: none;",
            )
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            self._format_buttons[plat_key] = {}
            for fmt_key, fmt_label in formats:
                fmt_btn = QPushButton(fmt_label)
                fmt_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
                fmt_btn.clicked.connect(
                    lambda _c, pk=plat_key, fk=fmt_key: self._on_format_clicked(pk, fk),
                )
                row_layout.addWidget(fmt_btn)
                self._format_buttons[plat_key][fmt_key] = fmt_btn

            layout.addWidget(row)
            self._format_rows[plat_key] = row

        if selected_platform:
            self.set_platform(selected_platform)
            if selected_format:
                self._select_format_internal(selected_platform, selected_format)
        elif self._platforms:
            first_key = self._platforms[0][0]
            self.set_platform(first_key)
            first_formats = self._platforms[0][2]
            if first_formats:
                self._select_format_internal(first_key, first_formats[0][0])

    def _on_format_clicked(self, platform_key: str, format_key: str) -> None:
        if self._selected_platform != platform_key:
            self.set_platform(platform_key)
        self._select_format_internal(platform_key, format_key)
        self.format_changed.emit(platform_key, format_key)

    def _select_format_internal(self, platform_key: str, format_key: str) -> None:
        self._selected_format = format_key
        for pk, buttons in self._format_buttons.items():
            for fk, btn in buttons.items():
                is_selected = pk == platform_key and fk == format_key
                if is_selected:
                    btn.setStyleSheet(
                        f"background: {Colors.PRIMARY_CONTAINER};"
                        f" color: {Colors.ON_PRIMARY_CONTAINER};"
                        f" border: none; border-radius: {Radii.DEFAULT}px;"
                        f" font-family: '{Typography.MONO}'; font-size: 10px;"
                        f" padding: 4px 8px;",
                    )
                else:
                    btn.setStyleSheet(
                        f"background: {Colors.SURFACE_CONTAINER_HIGH};"
                        f" color: {Colors.ON_SURFACE_VARIANT};"
                        f" border: none; border-radius: {Radii.DEFAULT}px;"
                        f" font-family: '{Typography.MONO}'; font-size: 10px;"
                        f" padding: 4px 8px;",
                    )

    def set_platform(self, name: str) -> None:
        """Select the platform identified by *name*."""
        prev = self._selected_platform
        self._selected_platform = name

        for key, row in self._format_rows.items():
            selected = key == name
            border_color = Colors.OUTLINE_VARIANT if selected else "transparent"
            row.setStyleSheet(
                f"background: rgba(51, 53, 57, {'0.5' if selected else '0.2'});"
                f" border: 1px solid {border_color};"
                f" border-radius: {Radii.DEFAULT}px;",
            )

        if prev != name:
            self.platform_changed.emit(name)
            for _pk, _pl, formats in self._platforms:
                if _pk == name and formats:
                    self._select_format_internal(name, formats[0][0])
                    break

    def set_format(self, platform: str, format_key: str) -> None:
        """Programmatically select a format for a platform."""
        self._select_format_internal(platform, format_key)

    def selected_platform_name(self) -> str:
        """Return the key of the currently selected platform."""
        return self._selected_platform

    def selected_format_name(self) -> str:
        """Return the key of the currently selected format."""
        return self._selected_format


class PlaybackControls(QWidget):
    """Play, skip-prev, and skip-next transport buttons."""

    play_clicked = Signal()
    skip_prev_clicked = Signal()
    skip_next_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._playing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.BASE)
        layout.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]

        skip_btn_ss = (
            f"QPushButton {{ background: {Colors.SURFACE_CONTAINER_HIGH};"
            f" color: {Colors.ON_SURFACE}; border: none; border-radius: 16px;"
            f" font-size: 14px; }}"
            f"QPushButton:hover {{ background: {Colors.SURFACE_VARIANT}; }}"
        )

        self._prev_btn = QPushButton()
        self._prev_btn.setIcon(MaterialIcon("skip_previous"))
        self._prev_btn.setIconSize(QSize(18, 18))
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setStyleSheet(skip_btn_ss)
        self._prev_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._prev_btn.clicked.connect(self.skip_prev_clicked)
        layout.addWidget(self._prev_btn)

        self._play_btn = QPushButton()
        self._play_btn.setIcon(MaterialIcon("play_arrow"))
        self._play_btn.setIconSize(QSize(18, 18))
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.PRIMARY_CONTAINER};"
            f" color: {Colors.ON_PRIMARY_CONTAINER}; border: none;"
            f" border-radius: 16px; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}",
        )
        self._play_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._play_btn.clicked.connect(self.play_clicked)
        layout.addWidget(self._play_btn)

        self._next_btn = QPushButton()
        self._next_btn.setIcon(MaterialIcon("skip_next"))
        self._next_btn.setIconSize(QSize(18, 18))
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setStyleSheet(skip_btn_ss)
        self._next_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        self._next_btn.clicked.connect(self.skip_next_clicked)
        layout.addWidget(self._next_btn)

    def set_playing(self, *, playing: bool) -> None:
        """Toggle the play button between play and pause icons."""
        self._playing = playing
        self._play_btn.setIcon(
            MaterialIcon("pause" if playing else "play_arrow"),
        )


class ProgressBar(QWidget):
    """Custom-painted horizontal progress bar."""

    def __init__(self, height: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._value: int = 0

    def set_value(self, value: int) -> None:
        """Set progress percentage (0-100)."""
        self._value = max(0, min(100, value))
        self.update()

    def value(self) -> int:
        """Return the current progress percentage."""
        return self._value

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the track and fill."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]

        h = self.height()
        w = self.width()
        radius = h / 2.0

        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(QColor(Colors.SURFACE_CONTAINER_HIGHEST))
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        if self._value > 0:
            fill_w = max(h, int(w * self._value / 100))
            p.setBrush(QColor(Colors.PRIMARY_CONTAINER))
            p.drawRoundedRect(0, 0, fill_w, h, radius, radius)

        p.end()


class RenderProgressItem(QWidget):
    """Single render task with label, percentage, and progress bar."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS - 2)

        header = QHBoxLayout()
        header.setSpacing(0)

        name_font = QFont(Typography.MONO)
        name_font.setPixelSize(Typography.LABEL_SM_SIZE)
        name_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))

        self._name_label = QLabel(label)
        self._name_label.setFont(name_font)
        self._name_label.setStyleSheet(f"color: {Colors.ON_SURFACE};")
        header.addWidget(self._name_label)

        header.addStretch()

        self._pct_label = QLabel("0%")
        self._pct_label.setFont(name_font)
        self._pct_label.setStyleSheet(f"color: {Colors.PRIMARY_CONTAINER};")
        header.addWidget(self._pct_label)

        layout.addLayout(header)

        self._progress = ProgressBar(height=4)
        layout.addWidget(self._progress)

    def set_progress(self, value: int) -> None:
        """Update the progress bar and percentage text."""
        value = max(0, min(100, value))
        self._progress.set_value(value)
        self._pct_label.setText(f"{value}%")

    def set_status(self, text: str) -> None:
        """Replace the percentage with a status string like 'Done'."""
        self._pct_label.setText(text)
