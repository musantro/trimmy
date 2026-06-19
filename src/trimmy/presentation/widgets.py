"""PySide6 widgets for crop selection, preview, and timeline."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from trimmy.crop.application.use_cases import (
    InitializeCropsRequest,
    InitializeCropsUseCase,
    MoveCropRequest,
    MoveCropUseCase,
    ResizeCropRequest,
    ResizeCropUseCase,
    SynchronizeAspectsRequest,
    SynchronizeAspectsUseCase,
)
from trimmy.crop.domain.models import (
    CropHandle,
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
)
from trimmy.crop.domain.services import CropAspects
from trimmy.crop.infrastructure.in_memory_crop_selection_repository import (
    InMemoryCropSelectionRepository,
)
from trimmy.trim.application.use_cases import (
    SetTrimEndRequest,
    SetTrimEndUseCase,
    SetTrimStartRequest,
    SetTrimStartUseCase,
)
from trimmy.trim.domain.models import TrimRange

_HANDLE_HIT_RADIUS = 10
_HANDLE_SIZE = 10

_CROP_COLORS: list[tuple[CropPosition, str]] = [
    (CropPosition.TOP, "#4ecdc4"),
    (CropPosition.BOTTOM, "#ffe66d"),
]


class CropWidget(QWidget):
    """Interactive overlay for dragging two crop rectangles on a frame."""

    crops_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.frame: QImage | None = None
        self.source = SourceSize(0, 0)
        self.aspects = CropAspects(1.0, 1.0)

        self._repository = InMemoryCropSelectionRepository()
        self._initialize = InitializeCropsUseCase(self._repository)
        self._synchronize = SynchronizeAspectsUseCase(self._repository)
        self._move = MoveCropUseCase(self._repository)
        self._resize = ResizeCropUseCase(self._repository)

        self._drag_position: CropPosition | None = None
        self._drag_handle: CropHandle | None = None
        self._drag_moving = False
        self._drag_start = QPointF()
        self._drag_origin = CropRect()

        self._vid_ox: float = 0.0
        self._vid_oy: float = 0.0
        self._vid_scale: float = 1.0

        self.setMouseTracking(True)  # noqa: FBT003
        self.setMinimumSize(400, 250)
        self.setSizePolicy(
            QSizePolicy.Expanding,  # ty: ignore[unresolved-attribute]
            QSizePolicy.Expanding,  # ty: ignore[unresolved-attribute]
        )

    @property
    def selection(self) -> CropSelection:
        """Return the current crop selection."""
        return self._repository.get()

    def set_selection(self, selection: CropSelection) -> None:
        """Replace the current crop selection."""
        self._repository.save(selection)
        self.update()

    def set_frame(self, image: QImage) -> None:
        """Update the displayed video frame."""
        self.frame = image
        self.update()

    def set_source_size(self, w: int, h: int) -> None:
        """Store the source video dimensions."""
        self.source = SourceSize(w, h)

    def init_crops(self) -> None:
        """Reset crop rectangles to default positions."""
        self._initialize.initialize(InitializeCropsRequest(self.source))
        self.update()

    def set_crop_aspects(self, top_aspect: float, bottom_aspect: float) -> None:
        """Set aspect ratios and re-sync both crop rectangles."""
        self.aspects = CropAspects(top=top_aspect, bottom=bottom_aspect)
        self._synchronize.synchronize(
            SynchronizeAspectsRequest(self.aspects, self.source),
        )
        self.update()
        self.crops_changed.emit()

    # ---- painting ----

    @override
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the video frame and crop overlays."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
        p.fillRect(self.rect(), QColor("#000000"))

        if self.frame is None or self.source.width == 0:
            p.setPen(QColor("#666"))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,  # ty: ignore[unresolved-attribute]
                "Open a video to begin",
            )
            return

        aspect = self.source.width / self.source.height
        dw = self.width()
        dh = int(dw / aspect)
        if dh > self.height():
            dh = self.height()
            dw = int(dh * aspect)
        ox = (self.width() - dw) // 2
        oy = (self.height() - dh) // 2
        self._vid_ox, self._vid_oy = ox, oy
        self._vid_scale = dw / self.source.width

        p.drawImage(
            QRectF(ox, oy, dw, dh),
            self.frame,
            QRectF(0, 0, self.frame.width(), self.frame.height()),
        )

        for position, hexcolor in _CROP_COLORS:
            self._paint_crop(p, position, QColor(hexcolor))

    def _paint_crop(
        self,
        p: QPainter,
        position: CropPosition,
        color: QColor,
    ) -> None:
        r = self._crop_display_rect(position)
        fill = QColor(color)
        fill.setAlpha(35)
        p.setPen(QPen(color, 2))
        p.setBrush(fill)
        p.drawRect(r)

        font = QFont()
        font.setBold(True)  # noqa: FBT003
        font.setPointSize(11)
        p.setFont(font)
        p.setPen(color)
        p.drawText(r, Qt.AlignCenter, position.value.upper())  # ty: ignore[unresolved-attribute]

        hs = _HANDLE_SIZE
        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(Qt.white)  # ty: ignore[unresolved-attribute]
        for cx, cy in [
            (r.left(), r.top()),
            (r.right(), r.top()),
            (r.left(), r.bottom()),
            (r.right(), r.bottom()),
        ]:
            p.drawRect(QRectF(cx - hs / 2, cy - hs / 2, hs, hs))

    # ---- coordinate helpers ----

    def _crop_display_rect(self, position: CropPosition) -> QRectF:
        c = self.selection.get(position)
        s = self._vid_scale
        return QRectF(
            self._vid_ox + c.x * s,
            self._vid_oy + c.y * s,
            c.w * s,
            c.h * s,
        )

    def _handle_centers(
        self,
        position: CropPosition,
    ) -> list[tuple[CropHandle, QPointF]]:
        r = self._crop_display_rect(position)
        return [
            (CropHandle.NW, QPointF(r.left(), r.top())),
            (CropHandle.NE, QPointF(r.right(), r.top())),
            (CropHandle.SW, QPointF(r.left(), r.bottom())),
            (CropHandle.SE, QPointF(r.right(), r.bottom())),
        ]

    def _widget_to_source(self, pos: QPointF) -> QPointF:
        return QPointF(
            (pos.x() - self._vid_ox) / self._vid_scale,
            (pos.y() - self._vid_oy) / self._vid_scale,
        )

    # ---- mouse interaction ----

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Begin a drag on a crop handle or body."""
        if self.source.width == 0:
            return
        pos = event.position()

        for position in (CropPosition.TOP, CropPosition.BOTTOM):
            for handle, center in self._handle_centers(position):
                if (pos - center).manhattanLength() < _HANDLE_HIT_RADIUS:
                    self._begin_drag(position, pos, handle=handle)
                    return

        for position in (CropPosition.TOP, CropPosition.BOTTOM):
            if self._crop_display_rect(position).contains(pos):
                self._begin_drag(position, pos, handle=None)
                return

    def _begin_drag(
        self,
        position: CropPosition,
        pos: QPointF,
        *,
        handle: CropHandle | None,
    ) -> None:
        self._drag_position = position
        self._drag_handle = handle
        self._drag_moving = handle is None
        self._drag_start = self._widget_to_source(pos)
        self._drag_origin = self.selection.get(position)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the active crop rectangle while dragging."""
        pos = event.position()

        if self._drag_position is None:
            self._update_cursor(pos)
            return

        src = self._widget_to_source(pos)
        dx = src.x() - self._drag_start.x()
        dy = src.y() - self._drag_start.y()

        if self._drag_moving:
            self._move.move(
                MoveCropRequest(
                    self._drag_position,
                    self._drag_origin,
                    dx,
                    dy,
                    self.source,
                ),
            )
        elif self._drag_handle is not None:
            aspect = (
                self.aspects.top
                if self._drag_position is CropPosition.TOP
                else self.aspects.bottom
            )
            self._resize.resize(
                ResizeCropRequest(
                    self._drag_position,
                    self._drag_handle,
                    self._drag_origin,
                    dx,
                    aspect,
                    self.source,
                ),
            )

        self.update()
        self.crops_changed.emit()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End the current drag operation."""
        self._drag_position = None
        self._drag_handle = None
        self._drag_moving = False

    def _update_cursor(self, pos: QPointF) -> None:
        for position in (CropPosition.TOP, CropPosition.BOTTOM):
            for handle, center in self._handle_centers(position):
                if (pos - center).manhattanLength() < _HANDLE_HIT_RADIUS:
                    cur = (
                        Qt.SizeFDiagCursor  # ty: ignore[unresolved-attribute]
                        if handle in (CropHandle.NW, CropHandle.SE)
                        else Qt.SizeBDiagCursor  # ty: ignore[unresolved-attribute]
                    )
                    self.setCursor(cur)
                    return
            if self._crop_display_rect(position).contains(pos):
                self.setCursor(Qt.SizeAllCursor)  # ty: ignore[unresolved-attribute]
                return
        self.setCursor(Qt.ArrowCursor)  # ty: ignore[unresolved-attribute]


class PreviewWidget(QWidget):
    """Live 9:16 preview showing the composited top/bottom crops."""

    split_ratio_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(270, 480)
        self.frame: QImage | None = None
        self.selection = CropSelection(top=CropRect(), bottom=CropRect())
        self.split_ratio: float = 0.5
        self._dragging: bool = False

    def set_frame(self, image: QImage) -> None:
        """Update the preview source frame."""
        self.frame = image
        self.update()

    def set_selection(self, selection: CropSelection) -> None:
        """Update the crop regions shown in the preview."""
        self.selection = selection
        self.update()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Render the composited preview with a split bar."""
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)  # ty: ignore[unresolved-attribute]
        p.fillRect(self.rect(), Qt.black)  # ty: ignore[unresolved-attribute]

        if self.frame is None:
            return

        top_h = int(self.height() * self.split_ratio)
        bot_h = self.height() - top_h

        tc = self.selection.top
        if not tc.is_empty:
            p.drawImage(
                QRectF(0, 0, self.width(), top_h),
                self.frame,
                QRectF(tc.x, tc.y, tc.w, tc.h),
            )

        bc = self.selection.bottom
        if not bc.is_empty:
            p.drawImage(
                QRectF(0, top_h, self.width(), bot_h),
                self.frame,
                QRectF(bc.x, bc.y, bc.w, bc.h),
            )

        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(QColor("#e94560"))
        p.drawRect(QRectF(0, top_h - 3, self.width(), 6))

        border = QColor("#333333")
        p.setPen(QPen(border, 2))
        p.setBrush(Qt.NoBrush)  # ty: ignore[unresolved-attribute]
        p.drawRoundedRect(
            self.rect().adjusted(1, 1, -1, -1),
            8,
            8,
        )

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start dragging the split bar if the click is near it."""
        top_h = self.height() * self.split_ratio
        if abs(event.position().y() - top_h) < 12:
            self._dragging = True

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Drag the split bar or update the cursor."""
        if not self._dragging:
            top_h = self.height() * self.split_ratio
            if abs(event.position().y() - top_h) < 12:
                self.setCursor(Qt.SplitVCursor)  # ty: ignore[unresolved-attribute]
            else:
                self.setCursor(Qt.ArrowCursor)  # ty: ignore[unresolved-attribute]
            return
        ratio = event.position().y() / self.height()
        self.split_ratio = max(0.15, min(0.85, ratio))
        self.update()
        self.split_ratio_changed.emit(self.split_ratio)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End the split-bar drag."""
        self._dragging = False


class TimelineWidget(QWidget):
    """Trim timeline with draggable start/end handles and seek."""

    range_changed = Signal(float, float)
    seek_requested = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.duration: float = 0.0
        self.trim_start: float = 0.0
        self.trim_end: float = 0.0
        self.position: float = 0.0
        self.setFixedHeight(72)
        self.setMinimumWidth(200)
        self._dragging: str | None = None
        self._set_start = SetTrimStartUseCase()
        self._set_end = SetTrimEndUseCase()

    @property
    def trim_range(self) -> TrimRange:
        """Return the current trim range as a domain value object."""
        return TrimRange(self.trim_start, self.trim_end)

    def set_duration(self, dur: float) -> None:
        """Set the total video duration and reset trim handles."""
        self.duration = dur
        full = TrimRange.full(dur)
        self.trim_start = full.start
        self.trim_end = full.end
        self.update()

    def set_position(self, pos: float) -> None:
        """Update the current playback position indicator."""
        self.position = pos
        self.update()

    def apply_range(self, trim_range: TrimRange) -> None:
        """Adopt *trim_range* and notify listeners."""
        self.trim_start = trim_range.start
        self.trim_end = trim_range.end
        self.update()
        self.range_changed.emit(self.trim_start, self.trim_end)

    def _bar(self) -> QRectF:
        return QRectF(20, 8, self.width() - 40, 36)

    def _t2x(self, t: float) -> float:
        bar = self._bar()
        if self.duration <= 0:
            return bar.left()
        return bar.left() + (t / self.duration) * bar.width()

    def _x2t(self, x: float) -> float:
        bar = self._bar()
        pct = (x - bar.left()) / bar.width()
        return max(0.0, min(self.duration, pct * self.duration))

    @override
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw the timeline bar, trim region, handles, and playhead."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
        bar = self._bar()

        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(QColor("#0a0a1a"))
        p.drawRoundedRect(bar, 6, 6)

        sx = self._t2x(self.trim_start)
        ex = self._t2x(self.trim_end)
        p.setBrush(QColor(233, 69, 96, 76))
        p.drawRoundedRect(
            QRectF(sx, bar.top(), ex - sx, bar.height()),
            6,
            6,
        )

        hw = 12
        for t in (self.trim_start, self.trim_end):
            hx = self._t2x(t)
            p.setBrush(QColor("#e94560"))
            p.drawRoundedRect(
                QRectF(hx - hw / 2, bar.top() - 4, hw, bar.height() + 8),
                3,
                3,
            )

        phx = self._t2x(self.position)
        p.setPen(QPen(Qt.white, 2))  # ty: ignore[unresolved-attribute]
        p.drawLine(
            QPointF(phx, bar.top()),
            QPointF(phx, bar.bottom()),
        )

        p.setPen(QColor("#aaaaaa"))
        font = QFont()
        font.setPointSize(9)
        p.setFont(font)
        y = bar.bottom() + 4
        p.drawText(
            QRectF(bar.left(), y, 120, 18),
            Qt.AlignLeft,  # ty: ignore[unresolved-attribute]
            self._fmt(self.trim_start),
        )
        dur_text = f"Duration: {self._fmt(self.trim_end - self.trim_start)}"
        p.drawText(
            QRectF(bar.left(), y, bar.width(), 18),
            Qt.AlignCenter,  # ty: ignore[unresolved-attribute]
            dur_text,
        )
        p.drawText(
            QRectF(bar.right() - 120, y, 120, 18),
            Qt.AlignRight,  # ty: ignore[unresolved-attribute]
            self._fmt(self.trim_end),
        )

    @staticmethod
    def _fmt(s: float) -> str:
        m = int(s // 60)
        sec = s % 60
        return f"{m}:{sec:04.1f}"

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Begin dragging a trim handle or seek to click position."""
        x = event.position().x()
        sx = self._t2x(self.trim_start)
        ex = self._t2x(self.trim_end)
        if abs(x - sx) < 10:
            self._dragging = "start"
        elif abs(x - ex) < 10:
            self._dragging = "end"
        elif self._bar().contains(event.position()):
            self.seek_requested.emit(self._x2t(x))

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Adjust the trim range while dragging a handle."""
        if self._dragging is None:
            return
        t = self._x2t(event.position().x())
        if self._dragging == "start":
            updated = self._set_start.set_start(
                SetTrimStartRequest(self.trim_range, t),
            )
            self.trim_start = updated.start
            self.seek_requested.emit(self.trim_start)
        else:
            updated = self._set_end.set_end(
                SetTrimEndRequest(self.trim_range, t, self.duration),
            )
            self.trim_end = updated.end
            self.seek_requested.emit(self.trim_end)
        self.update()
        self.range_changed.emit(self.trim_start, self.trim_end)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End the trim-handle drag."""
        self._dragging = None
