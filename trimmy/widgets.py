"""PySide6 widgets for crop selection, preview, and timeline."""

import copy

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from trimmy.renderer import CropRect


class CropWidget(QWidget):
    """Interactive overlay for dragging two crop rectangles on a video frame."""

    crops_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.frame: QImage | None = None
        self.source_w = 0
        self.source_h = 0
        self.crops = {"top": CropRect(), "bottom": CropRect()}
        self.crop_aspects = {"top": 1.0, "bottom": 1.0}

        self._drag_key: str | None = None
        self._drag_type: str | None = None
        self._drag_start = QPointF()
        self._drag_orig = CropRect()

        self._vid_ox = 0.0
        self._vid_oy = 0.0
        self._vid_scale = 1.0

        self.setMouseTracking(True)  # noqa: FBT003
        self.setMinimumSize(400, 250)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

    def set_frame(self, image: QImage) -> None:
        """Update the displayed video frame."""
        self.frame = image
        self.update()

    def set_source_size(self, w: int, h: int) -> None:
        """Store the source video dimensions."""
        self.source_w = w
        self.source_h = h

    def init_crops(self) -> None:
        """Reset crop rectangles to default positions."""
        w = self.source_w * 0.6
        h = self.source_h * 0.45
        self.crops["top"] = CropRect(0, 0, w, h)
        self.crops["bottom"] = CropRect(
            self.source_w * 0.2,
            self.source_h * 0.5,
            w,
            h,
        )

    def set_crop_aspects(
        self,
        top_aspect: float,
        bottom_aspect: float,
    ) -> None:
        """Set aspect ratios and re-sync both crop rectangles."""
        self.crop_aspects["top"] = top_aspect
        self.crop_aspects["bottom"] = bottom_aspect
        self._sync_aspect("top")
        self._sync_aspect("bottom")
        self.update()
        self.crops_changed.emit()

    def _sync_aspect(self, key: str) -> None:
        c = self.crops[key]
        aspect = self.crop_aspects[key]
        new_h = c.w / aspect
        clamped_h = min(new_h, self.source_h)
        final_w = clamped_h * aspect
        c.w = min(final_w, self.source_w)
        c.h = clamped_h
        if c.x + c.w > self.source_w:
            c.x = self.source_w - c.w
        if c.y + c.h > self.source_h:
            c.y = self.source_h - c.h
        c.x = max(0, c.x)
        c.y = max(0, c.y)

    # ---- painting ----

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the video frame and crop overlays."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#000000"))

        if self.frame is None or self.source_w == 0:
            p.setPen(QColor("#666"))
            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Open a video to begin",
            )
            return

        aspect = self.source_w / self.source_h
        dw = self.width()
        dh = int(dw / aspect)
        if dh > self.height():
            dh = self.height()
            dw = int(dh * aspect)
        ox = (self.width() - dw) // 2
        oy = (self.height() - dh) // 2
        self._vid_ox, self._vid_oy = ox, oy
        self._vid_scale = dw / self.source_w

        p.drawImage(
            QRectF(ox, oy, dw, dh),
            self.frame,
            QRectF(0, 0, self.frame.width(), self.frame.height()),
        )

        for key, color in [
            ("top", QColor("#4ecdc4")),
            ("bottom", QColor("#ffe66d")),
        ]:
            self._paint_crop(p, key, color)

    def _paint_crop(self, p: QPainter, key: str, color: QColor) -> None:
        r = self._crop_display_rect(key)
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
        p.drawText(r, Qt.AlignCenter, key.upper())

        hs = 10
        p.setPen(Qt.NoPen)
        p.setBrush(Qt.white)
        for cx, cy in [
            (r.left(), r.top()),
            (r.right(), r.top()),
            (r.left(), r.bottom()),
            (r.right(), r.bottom()),
        ]:
            p.drawRect(QRectF(cx - hs / 2, cy - hs / 2, hs, hs))

    # ---- coordinate helpers ----

    def _crop_display_rect(self, key: str) -> QRectF:
        c = self.crops[key]
        s = self._vid_scale
        return QRectF(
            self._vid_ox + c.x * s,
            self._vid_oy + c.y * s,
            c.w * s,
            c.h * s,
        )

    def _handle_centers(self, key: str) -> list[tuple[str, QPointF]]:
        r = self._crop_display_rect(key)
        return [
            ("nw", QPointF(r.left(), r.top())),
            ("ne", QPointF(r.right(), r.top())),
            ("sw", QPointF(r.left(), r.bottom())),
            ("se", QPointF(r.right(), r.bottom())),
        ]

    def _widget_to_source(self, pos: QPointF) -> QPointF:
        return QPointF(
            (pos.x() - self._vid_ox) / self._vid_scale,
            (pos.y() - self._vid_oy) / self._vid_scale,
        )

    # ---- mouse interaction ----

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Begin a drag on a crop handle or body."""
        if self.source_w == 0:
            return
        pos = event.position()
        hit_radius = 10

        for key in ("top", "bottom"):
            for hname, hcenter in self._handle_centers(key):
                if (pos - hcenter).manhattanLength() < hit_radius:
                    self._drag_key = key
                    self._drag_type = f"resize_{hname}"
                    self._drag_start = self._widget_to_source(pos)
                    self._drag_orig = copy.copy(self.crops[key])
                    return

        for key in ("top", "bottom"):
            if self._crop_display_rect(key).contains(pos):
                self._drag_key = key
                self._drag_type = "move"
                self._drag_start = self._widget_to_source(pos)
                self._drag_orig = copy.copy(self.crops[key])
                return

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Update the active crop rectangle while dragging."""
        pos = event.position()

        if self._drag_key is None:
            self._update_cursor(pos)
            return

        src = self._widget_to_source(pos)
        dx = src.x() - self._drag_start.x()
        dy = src.y() - self._drag_start.y()
        o = self._drag_orig

        if self._drag_type == "move":
            nx = max(0, min(o.x + dx, self.source_w - o.w))
            ny = max(0, min(o.y + dy, self.source_h - o.h))
            self.crops[self._drag_key].x = nx
            self.crops[self._drag_key].y = ny
        else:
            handle = self._drag_type.split("_")[1]
            aspect = self.crop_aspects[self._drag_key]
            is_left = handle in ("nw", "sw")
            is_top = handle in ("nw", "ne")

            w = o.w - dx if is_left else o.w + dx
            w = max(30, w)
            h = w / aspect

            x = (o.x + o.w - w) if is_left else o.x
            y = (o.y + o.h - h) if is_top else o.y

            x = max(0, x)
            y = max(0, y)
            if x + w > self.source_w:
                w = self.source_w - x
                h = w / aspect
            if y + h > self.source_h:
                h = self.source_h - y
                w = h * aspect

            self.crops[self._drag_key] = CropRect(x, y, w, h)

        self.update()
        self.crops_changed.emit()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """End the current drag operation."""
        self._drag_key = None
        self._drag_type = None

    def _update_cursor(self, pos: QPointF) -> None:
        hit = 10
        for key in ("top", "bottom"):
            for hname, hcenter in self._handle_centers(key):
                if (pos - hcenter).manhattanLength() < hit:
                    cur = (
                        Qt.SizeFDiagCursor
                        if hname in ("nw", "se")
                        else Qt.SizeBDiagCursor
                    )
                    self.setCursor(cur)
                    return
            if self._crop_display_rect(key).contains(pos):
                self.setCursor(Qt.SizeAllCursor)
                return
        self.setCursor(Qt.ArrowCursor)


class PreviewWidget(QWidget):
    """Live 9:16 preview showing the composited top/bottom crops."""

    split_ratio_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(270, 480)
        self.frame: QImage | None = None
        self.crops = {"top": CropRect(), "bottom": CropRect()}
        self.split_ratio = 0.5
        self._dragging = False

    def set_frame(self, image: QImage) -> None:
        """Update the preview source frame."""
        self.frame = image
        self.update()

    def set_crops(self, top: CropRect, bottom: CropRect) -> None:
        """Update the crop regions shown in the preview."""
        self.crops["top"] = copy.copy(top)
        self.crops["bottom"] = copy.copy(bottom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Render the composited preview with a split bar."""
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), Qt.black)

        if self.frame is None:
            return

        top_h = int(self.height() * self.split_ratio)
        bot_h = self.height() - top_h

        tc = self.crops["top"]
        if tc.w > 0 and tc.h > 0:
            p.drawImage(
                QRectF(0, 0, self.width(), top_h),
                self.frame,
                QRectF(tc.x, tc.y, tc.w, tc.h),
            )

        bc = self.crops["bottom"]
        if bc.w > 0 and bc.h > 0:
            p.drawImage(
                QRectF(0, top_h, self.width(), bot_h),
                self.frame,
                QRectF(bc.x, bc.y, bc.w, bc.h),
            )

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#e94560"))
        p.drawRect(QRectF(0, top_h - 3, self.width(), 6))

        border = QColor("#333333")
        p.setPen(QPen(border, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(
            self.rect().adjusted(1, 1, -1, -1),
            8,
            8,
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Start dragging the split bar if the click is near it."""
        top_h = self.height() * self.split_ratio
        if abs(event.position().y() - top_h) < 12:
            self._dragging = True

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Drag the split bar or update the cursor."""
        if not self._dragging:
            top_h = self.height() * self.split_ratio
            if abs(event.position().y() - top_h) < 12:
                self.setCursor(Qt.SplitVCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return
        ratio = event.position().y() / self.height()
        self.split_ratio = max(0.15, min(0.85, ratio))
        self.update()
        self.split_ratio_changed.emit(self.split_ratio)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """End the split-bar drag."""
        self._dragging = False


class TimelineWidget(QWidget):
    """Trim timeline with draggable start/end handles and seek."""

    range_changed = Signal(float, float)
    seek_requested = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.duration = 0.0
        self.trim_start = 0.0
        self.trim_end = 0.0
        self.position = 0.0
        self.setFixedHeight(72)
        self.setMinimumWidth(200)
        self._dragging: str | None = None

    def set_duration(self, dur: float) -> None:
        """Set the total video duration and reset trim handles."""
        self.duration = dur
        self.trim_start = 0
        self.trim_end = dur
        self.update()

    def set_position(self, pos: float) -> None:
        """Update the current playback position indicator."""
        self.position = pos
        self.update()

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
        return max(0, min(self.duration, pct * self.duration))

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the timeline bar, trim region, handles, and playhead."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bar = self._bar()

        p.setPen(Qt.NoPen)
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
        p.setPen(QPen(Qt.white, 2))
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
            Qt.AlignLeft,
            self._fmt(self.trim_start),
        )
        dur_text = (
            f"Duration: {self._fmt(self.trim_end - self.trim_start)}"
        )
        p.drawText(
            QRectF(bar.left(), y, bar.width(), 18),
            Qt.AlignCenter,
            dur_text,
        )
        p.drawText(
            QRectF(bar.right() - 120, y, 120, 18),
            Qt.AlignRight,
            self._fmt(self.trim_end),
        )

    @staticmethod
    def _fmt(s: float) -> str:
        m = int(s // 60)
        sec = s % 60
        return f"{m}:{sec:04.1f}"

    def mousePressEvent(self, event) -> None:  # noqa: N802
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

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Adjust the trim range while dragging a handle."""
        if self._dragging is None:
            return
        t = self._x2t(event.position().x())
        if self._dragging == "start":
            self.trim_start = max(0, min(t, self.trim_end - 0.1))
            self.seek_requested.emit(self.trim_start)
        else:
            self.trim_end = min(
                self.duration,
                max(t, self.trim_start + 0.1),
            )
            self.seek_requested.emit(self.trim_end)
        self.update()
        self.range_changed.emit(self.trim_start, self.trim_end)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """End the trim-handle drag."""
        self._dragging = None
