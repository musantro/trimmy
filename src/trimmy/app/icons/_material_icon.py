"""
Minimal Material Symbols icon, rendered from vendored SVG data.

A drop-in replacement for ``qt_material_icons.MaterialIcon`` covering the
subset of behaviour Trimmy relies on: construction by glyph name and the
palette-tinted :meth:`pixmap`. Icons are recoloured to the application
palette's ``WindowText`` colour, matching the upstream package.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from trimmy.shared.compat import override

from ._data import ICON_SVGS

_DEFAULT_SIZE = 20


def _render(data: QByteArray, size: QSize) -> QPixmap:
    """Rasterise ``data`` (an SVG document) into a transparent pixmap."""
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(data)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(pixmap.rect()))
    painter.end()
    return pixmap


def _fill(pixmap: QPixmap, color: QColor) -> QPixmap:
    """Return a copy of ``pixmap`` tinted with ``color``."""
    tinted = QPixmap(pixmap)
    painter = QPainter(tinted)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), color)
    painter.end()
    return tinted


class MaterialIcon(QIcon):
    """A recolourable Material Symbols icon backed by vendored SVG data."""

    @override
    def __init__(self, name: str, size: int = _DEFAULT_SIZE) -> None:
        super().__init__()
        self.name: str = name
        self._data = QByteArray(ICON_SVGS[name])
        self._size = QSize(size, size)
        self._pixmap = _render(self._data, self._size)

        palette = QApplication.palette()
        self._color_normal = palette.color(
            QPalette.ColorGroup.Normal, QPalette.ColorRole.WindowText
        )
        self._color_disabled = palette.color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText
        )
        self.addPixmap(
            _fill(self._pixmap, self._color_normal),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
        self.addPixmap(
            _fill(self._pixmap, self._color_disabled),
            QIcon.Mode.Disabled,
            QIcon.State.Off,
        )

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"

    def colored_pixmap(self, size: QSize | int, color: QColor) -> QPixmap:
        """Return a ``color``-tinted pixmap, re-rasterising the SVG when resized."""
        if isinstance(size, int):
            target = QSize(size, size) if size else self._size
        else:
            target = size if size.isValid() else self._size

        pixmap = self._pixmap if target == self._size else _render(self._data, target)
        return _fill(pixmap, color)
