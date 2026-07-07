"""PySide6 widgets for crop selection, preview, and timeline."""

from __future__ import annotations

import array
import math
import sys

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat
from PySide6.QtWidgets import QSizePolicy, QWidget

from trimmy.app.theme import Colors, Typography
from trimmy.editing.crop.application.flip_output_areas_use_case import (
    FlipOutputAreasRequest,
    FlipOutputAreasUseCase,
)
from trimmy.editing.crop.application.initialize_crops_use_case import (
    InitializeCropsRequest,
    InitializeCropsUseCase,
)
from trimmy.editing.crop.application.move_crop_use_case import (
    MoveCropRequest,
    MoveCropUseCase,
)
from trimmy.editing.crop.application.resize_crop_use_case import (
    ResizeCropRequest,
    ResizeCropUseCase,
)
from trimmy.editing.crop.application.synchronize_aspects_use_case import (
    SynchronizeAspectsRequest,
    SynchronizeAspectsUseCase,
)
from trimmy.editing.crop.domain.services import CropAspects
from trimmy.editing.crop.infrastructure.in_memory_crop_selection_repository import (
    InMemoryCropSelectionRepository,
)
from trimmy.editing.shared.domain.models import (
    CropHandle,
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
    TrimRange,
)
from trimmy.editing.trim.application.set_trim_end_use_case import (
    SetTrimEndRequest,
    SetTrimEndUseCase,
)
from trimmy.editing.trim.application.set_trim_start_use_case import (
    SetTrimStartRequest,
    SetTrimStartUseCase,
)

_HANDLE_HIT_RADIUS = 10
_HANDLE_SIZE = 10

_CROP_COLORS: list[tuple[CropPosition, str]] = [
    (CropPosition.TOP, Colors.TERTIARY),
    (CropPosition.BOTTOM, Colors.PRIMARY_CONTAINER),
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
        self._flip_output = FlipOutputAreasUseCase(self._repository)
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

        self.setMouseTracking(True)
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

    def flip_output_areas(self, split_ratio: float) -> float:
        """Swap top and bottom crop properties and return the new split ratio."""
        result = self._flip_output.flip(FlipOutputAreasRequest(split_ratio))
        self.update()
        self.crops_changed.emit()
        return result.split_ratio

    # ---- painting ----

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the video frame and crop overlays."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
        p.fillRect(self.rect(), QColor(Colors.LEVEL_0))

        if self.frame is None or self.source.width == 0:
            p.setPen(QColor(Colors.OUTLINE))
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

        font = QFont(Typography.MONO)
        font.setPixelSize(Typography.LABEL_MD_SIZE)
        font.setWeight(QFont.Weight(Typography.LABEL_MD_WEIGHT))
        p.setFont(font)
        p.setPen(color)
        p.drawText(r, Qt.AlignCenter, position.value.upper())  # ty: ignore[unresolved-attribute]

        hs = _HANDLE_SIZE
        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(QColor(Colors.ON_SURFACE))
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
    def mousePressEvent(self, event: QMouseEvent) -> None:
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
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
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

    ASPECT_W = 9
    ASPECT_H = 16

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(90, 160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)  # ty: ignore[unresolved-attribute]
        self.frame: QImage | None = None
        self.selection = CropSelection(top=CropRect(), bottom=CropRect())
        self.split_ratio: float = 0.5
        self._dragging: bool = False
        self._hover: bool = False
        self.dimmed: bool = False
        self.interactive: bool = True
        self.setMouseTracking(True)

    def _preview_rect(self) -> QRectF:
        """Return the centered 9:16 rect that fits inside the widget."""
        w = self.width()
        h = self.height()
        fit_w = int(h * self.ASPECT_W / self.ASPECT_H)
        fit_h = int(w * self.ASPECT_H / self.ASPECT_W)
        if fit_w <= w:
            x = (w - fit_w) / 2
            return QRectF(x, 0, fit_w, h)
        y = (h - fit_h) / 2
        return QRectF(0, y, w, fit_h)

    def set_frame(self, image: QImage) -> None:
        """Update the preview source frame."""
        self.frame = image
        self.update()

    def set_selection(self, selection: CropSelection) -> None:
        """Update the crop regions shown in the preview."""
        self.selection = selection
        self.update()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the composited preview with a split bar."""
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)  # ty: ignore[unresolved-attribute]
        p.fillRect(self.rect(), QColor(Colors.LEVEL_0))

        r = self._preview_rect()
        if self.frame is None:
            border = QColor(Colors.LEVEL_1_BORDER)
            p.setPen(QPen(border, 2))
            p.setBrush(Qt.NoBrush)  # ty: ignore[unresolved-attribute]
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)
            return

        top_h = int(r.height() * self.split_ratio)
        bot_h = int(r.height()) - top_h

        tc = self.selection.top
        if not tc.is_empty:
            p.drawImage(
                QRectF(r.x(), r.y(), r.width(), top_h),
                self.frame,
                QRectF(tc.x, tc.y, tc.w, tc.h),
            )

        bc = self.selection.bottom
        if not bc.is_empty:
            p.drawImage(
                QRectF(r.x(), r.y() + top_h, r.width(), bot_h),
                self.frame,
                QRectF(bc.x, bc.y, bc.w, bc.h),
            )

        if self.interactive and (self._hover or self._dragging):
            p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
            p.setBrush(QColor(Colors.PRIMARY))
            p.drawRect(QRectF(r.x(), r.y() + top_h - 3, r.width(), 6))

        border = QColor(Colors.LEVEL_1_BORDER)
        p.setPen(QPen(border, 2))
        p.setBrush(Qt.NoBrush)  # ty: ignore[unresolved-attribute]
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

        if self.dimmed:
            p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 8, 8)

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        """Reveal the split bar while the cursor is over the preview."""
        self._hover = True
        self.update()

    @override
    def leaveEvent(self, event: QEvent) -> None:
        """Hide the split bar once the cursor leaves the preview."""
        self._hover = False
        self.update()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start dragging the split bar if the click is near it."""
        if not self.interactive:
            return
        r = self._preview_rect()
        top_h = r.y() + r.height() * self.split_ratio
        if abs(event.position().y() - top_h) < 12:
            self._dragging = True

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Drag the split bar or update the cursor."""
        if not self.interactive:
            return
        r = self._preview_rect()
        top_h = r.y() + r.height() * self.split_ratio
        if not self._dragging:
            if abs(event.position().y() - top_h) < 12:
                self.setCursor(Qt.SplitVCursor)  # ty: ignore[unresolved-attribute]
            else:
                self.setCursor(Qt.ArrowCursor)  # ty: ignore[unresolved-attribute]
            return
        ratio = (event.position().y() - r.y()) / r.height()
        self.split_ratio = max(0.15, min(0.85, ratio))
        self.update()
        self.split_ratio_changed.emit(self.split_ratio)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End the split-bar drag."""
        if not self.interactive:
            return
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
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the timeline bar, trim region, handles, and playhead."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
        bar = self._bar()

        p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
        p.setBrush(QColor(Colors.SURFACE_CONTAINER_LOWEST))
        p.drawRoundedRect(bar, 6, 6)

        sx = self._t2x(self.trim_start)
        ex = self._t2x(self.trim_end)
        trim_fill = QColor(Colors.PRIMARY)
        trim_fill.setAlpha(76)
        p.setBrush(trim_fill)
        p.drawRoundedRect(
            QRectF(sx, bar.top(), ex - sx, bar.height()),
            6,
            6,
        )

        hw = 12
        for t in (self.trim_start, self.trim_end):
            hx = self._t2x(t)
            p.setBrush(QColor(Colors.PRIMARY))
            p.drawRoundedRect(
                QRectF(hx - hw / 2, bar.top() - 4, hw, bar.height() + 8),
                3,
                3,
            )

        phx = self._t2x(self.position)
        p.setPen(QPen(QColor(Colors.ON_SURFACE), 2))
        p.drawLine(
            QPointF(phx, bar.top()),
            QPointF(phx, bar.bottom()),
        )

        p.setPen(QColor(Colors.ON_SURFACE_VARIANT))
        font = QFont(Typography.MONO)
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
    def mousePressEvent(self, event: QMouseEvent) -> None:
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
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End the trim-handle drag."""
        self._dragging = None


class AudioLevelMeter(QWidget):
    """Multi-channel audio meter showing live RMS levels in dBFS."""

    _MIN_DB = -60.0
    _MAX_DB = 0.0

    def __init__(self) -> None:
        super().__init__()
        self._channels = 0
        self._sample_rate = 0
        self._codec = ""
        self._levels: list[float] = []
        self.setMinimumWidth(240)
        self.setFixedHeight(88)

    def configure(
        self,
        *,
        channels: int,
        sample_rate: int = 0,
        codec: str = "",
    ) -> None:
        """Configure the visible channels and static audio metadata."""
        self._channels = max(0, channels)
        self._sample_rate = max(0, sample_rate)
        self._codec = codec.upper()
        self._levels = [self._MIN_DB] * self._channels
        self.setFixedHeight(56 + max(1, self._channels) * 22)
        self.update()

    def reset_levels(self) -> None:
        """Clear the meter to silence."""
        self._levels = [self._MIN_DB] * self._channels
        self.update()

    def set_levels(self, levels: list[float]) -> None:
        """Set current channel levels in dBFS."""
        if self._channels == 0:
            return
        trimmed = levels[: self._channels]
        padded = trimmed + [self._MIN_DB] * (self._channels - len(trimmed))
        self._levels = [max(self._MIN_DB, min(self._MAX_DB, level)) for level in padded]
        self.update()

    def set_buffer(self, buffer: QAudioBuffer) -> None:
        """Update live levels from a Qt audio buffer."""
        if not buffer.isValid():
            self.reset_levels()
            return
        levels = self._levels_from_buffer(buffer)
        if levels:
            self.set_levels(levels)

    def _levels_from_buffer(self, buffer: QAudioBuffer) -> list[float]:
        fmt = buffer.format()
        channels = fmt.channelCount()
        if channels <= 0:
            return []

        raw = self._buffer_bytes(buffer)
        sample_width = fmt.bytesPerSample()
        sample_count = len(raw) // sample_width if sample_width else 0
        frame_count = min(buffer.frameCount(), sample_count // channels)
        if frame_count <= 0:
            return []

        values = self._normalized_samples(raw, fmt)
        if not values:
            return []

        sums = [0.0] * channels
        usable = frame_count * channels
        for idx, sample in enumerate(values[:usable]):
            sums[idx % channels] += sample * sample

        return [self._rms_to_db(math.sqrt(total / frame_count)) for total in sums]

    @staticmethod
    def _buffer_bytes(buffer: QAudioBuffer) -> bytes:
        try:
            return bytes(buffer.constData())
        except TypeError:
            data = buffer.constData()
            if isinstance(data, memoryview):
                return data.tobytes()
            if isinstance(data, bytearray):
                return bytes(data)
            return b""

    @staticmethod
    def _normalized_samples(
        raw: bytes,
        fmt: QAudioFormat,
    ) -> list[float]:
        sample_format = fmt.sampleFormat()
        if sample_format == QAudioFormat.SampleFormat.UInt8:
            return [(value - 128) / 128.0 for value in raw]

        if sample_format == QAudioFormat.SampleFormat.Int16:
            samples = array.array("h")
            samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
            return [max(-1.0, sample / 32768.0) for sample in samples]

        if sample_format == QAudioFormat.SampleFormat.Int32:
            samples = array.array("i")
            samples.frombytes(raw[: len(raw) - (len(raw) % 4)])
            return [max(-1.0, sample / 2147483648.0) for sample in samples]

        if sample_format == QAudioFormat.SampleFormat.Float:
            samples = array.array("f")
            samples.frombytes(raw[: len(raw) - (len(raw) % 4)])
            return [max(-1.0, min(1.0, sample)) for sample in samples]

        return []

    @classmethod
    def _rms_to_db(cls, rms: float) -> float:
        if rms <= 0.000001:
            return cls._MIN_DB
        return 20.0 * math.log10(rms)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw channel labels, dB readouts, and level bars."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)  # ty: ignore[unresolved-attribute]
        p.fillRect(self.rect(), QColor(Colors.SURFACE_CONTAINER_LOW))

        title_font = QFont(Typography.MONO)
        title_font.setPixelSize(Typography.LABEL_SM_SIZE)
        title_font.setWeight(QFont.Weight(Typography.LABEL_SM_WEIGHT))
        p.setFont(title_font)
        p.setPen(QColor(Colors.ON_SURFACE_VARIANT))

        meta = "NO AUDIO"
        if self._channels:
            rate = f"{self._sample_rate // 1000} KHZ" if self._sample_rate else ""
            parts = [f"{self._channels} CH", rate, self._codec]
            meta = " · ".join(part for part in parts if part)
        p.drawText(
            QRectF(12, 8, self.width() - 24, 18),
            Qt.AlignLeft,  # ty: ignore[unresolved-attribute]
            f"AUDIO CHANNELS  {meta}",
        )

        if self._channels == 0:
            p.setPen(QColor(Colors.OUTLINE))
            p.drawText(
                QRectF(12, 32, self.width() - 24, 18),
                Qt.AlignLeft,  # ty: ignore[unresolved-attribute]
                "No audio streams detected",
            )
            return

        label_w = 44
        value_w = 62
        bar_left = 12 + label_w
        bar_right = self.width() - 12 - value_w
        bar_w = max(24, bar_right - bar_left)
        row_top = 34
        row_h = 22

        row_font = QFont(Typography.MONO)
        row_font.setPixelSize(10)
        p.setFont(row_font)

        for index in range(self._channels):
            y = row_top + index * row_h
            level = self._levels[index] if index < len(self._levels) else self._MIN_DB
            pct = (level - self._MIN_DB) / (self._MAX_DB - self._MIN_DB)

            p.setPen(QColor(Colors.ON_SURFACE_VARIANT))
            p.drawText(
                QRectF(12, y, label_w - 8, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"CH {index + 1}",
            )

            bar = QRectF(bar_left, y + 4, bar_w, 8)
            p.setPen(Qt.NoPen)  # ty: ignore[unresolved-attribute]
            p.setBrush(QColor(Colors.SURFACE_CONTAINER_HIGHEST))
            p.drawRoundedRect(bar, 4, 4)

            fill_w = max(2.0, bar.width() * pct) if level > self._MIN_DB else 0.0
            if fill_w > 0:
                color = Colors.ERROR if level > -6 else Colors.PRIMARY_CONTAINER
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(bar.x(), bar.y(), fill_w, bar.height()), 4, 4)

            p.setPen(QColor(Colors.ON_SURFACE))
            p.drawText(
                QRectF(bar_right + 8, y, value_w - 8, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{level:5.1f} dB",
            )
