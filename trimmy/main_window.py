"""Main application window, render thread, and drop overlay."""

from __future__ import annotations

import logging
import math
import shutil
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFont,
    QImage,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from trimmy import config
from trimmy.presets import PLATFORM_FORMATS, PLATFORM_INFO
from trimmy.renderer import CropRect, RenderContext, probe_video, render_video
from trimmy.widgets import CropWidget, PreviewWidget, TimelineWidget

logger = logging.getLogger(__name__)

_STYLE_ERROR = (
    "background: #4a1a1a; color: #e94560; padding: 8px 12px; border-radius: 6px;"
)
_STYLE_SUCCESS = (
    "background: #1a4a2e; color: #4ecdc4; padding: 8px 12px; border-radius: 6px;"
)


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
        p.fillRect(self.rect(), QColor(10, 10, 30, 200))

        border = QColor("#e94560")
        pen = QPen(border, 3, Qt.DashLine)  # ty: ignore[unresolved-attribute]
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)  # ty: ignore[unresolved-attribute]
        margin = 40
        p.drawRoundedRect(
            margin,
            margin,
            self.width() - 2 * margin,
            self.height() - 2 * margin,
            16,
            16,
        )

        p.setPen(QColor("#e94560"))
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)  # noqa: FBT003
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "Drop video here")  # ty: ignore[unresolved-attribute]

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Forward resize to the base class."""
        super().resizeEvent(event)


STYLESHEET = """\
QMainWindow, QWidget#central { background: #1a1a2e; }
QLabel { color: #e0e0e0; }
QPushButton {
    background: #0f3460; color: #e0e0e0; border: none; border-radius: 6px;
    padding: 8px 16px; font-size: 13px; font-weight: 600;
}
QPushButton:hover { background: #1a4a80; }
QPushButton:checked { background: #e94560; color: #fff; }
QPushButton:disabled { background: #444; color: #888; }
QPushButton#render { background: #e94560; color: #fff; }
QPushButton#render:hover { background: #d63851; }
QPushButton#render:disabled { background: #555; color: #888; }
QPushButton#stop { background: #e07020; color: #fff; }
QPushButton#stop:hover { background: #f08030; }
QLabel#section {
    color: #aaa; font-size: 12px;
    text-transform: uppercase; letter-spacing: 1px;
}
QLabel#status { padding: 8px 12px; border-radius: 6px; font-size: 13px; }
QLabel#info { color: #888; font-size: 12px; }
QMenu {
    background: #16213e; color: #e0e0e0; border: 1px solid #0f3460;
    border-radius: 4px; padding: 4px 0;
}
QMenu::item { padding: 8px 20px; font-size: 13px; }
QMenu::item:selected { background: #1a4a80; }
"""


class RenderThread(QThread):
    """Background thread that runs one or more render passes."""

    finished = Signal(object)
    progress = Signal(int, int)

    def __init__(
        self,
        max_duration: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._kwargs = kwargs
        self._max_duration = max_duration
        self._ctx = RenderContext()

    def stop(self) -> None:
        """Request cancellation of the running render."""
        self._ctx.cancel()

    @override
    def run(self) -> None:  # noqa: D102
        trim_start = self._kwargs["trim_start"]
        trim_end = self._kwargs["trim_end"]
        total_duration = trim_end - trim_start

        if self._max_duration is None or total_duration <= self._max_duration:
            result = render_video(**self._kwargs, ctx=self._ctx)
            self.finished.emit(result)
            return

        num_parts = math.ceil(total_duration / self._max_duration)
        out_path = self._kwargs["out_path"]
        results: list[dict[str, Any]] = []

        for i in range(num_parts):
            if self._ctx.cancelled:
                results.append({"error": "Cancelled"})
                break
            self.progress.emit(i + 1, num_parts)
            seg_start = trim_start + i * self._max_duration
            seg_end = min(
                trim_start + (i + 1) * self._max_duration,
                trim_end,
            )
            seg_path = out_path.parent / f"{out_path.stem}_part{i + 1}.mp4"

            seg_kwargs = dict(self._kwargs)
            seg_kwargs["trim_start"] = seg_start
            seg_kwargs["trim_end"] = seg_end
            seg_kwargs["out_path"] = seg_path

            result = render_video(**seg_kwargs, ctx=self._ctx)
            result["part"] = i + 1
            result["total_parts"] = num_parts
            result["path"] = str(seg_path)
            results.append(result)

            if "error" in result:
                break

        self.finished.emit(results)


class MainWindow(QMainWindow):
    """Primary application window with crop, preview, and render controls."""

    def __init__(self, file_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Trimmy")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(STYLESHEET)

        self.setAcceptDrops(True)  # noqa: FBT003

        self.video_info: dict[str, Any] | None = None
        self.current_frame: QImage | None = None
        self._cfg = config.load()
        self.selected_platform: str = self._cfg["selected_platform"]
        self.selected_format: str = self._cfg["selected_format"]
        self.selected_quality: str = self._cfg["selected_quality"]
        self.split_ratio: float = self._cfg["split_ratio"]
        self._waiting_first_frame: bool = False
        self._render_thread: RenderThread | None = None

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.audio.setMuted(True)  # noqa: FBT003
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink()
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.player.positionChanged.connect(self._on_position)

        self._build_ui()

        if file_path:
            self.open_file(file_path)

    # ---- UI construction ----

    def _build_ui(self) -> None:  # noqa: PLR0915
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(20)
        root.setContentsMargins(20, 20, 20, 20)

        left = QVBoxLayout()
        left.setSpacing(12)

        self.crop_widget = CropWidget()
        left.addWidget(self.crop_widget, stretch=1)

        self.timeline = TimelineWidget()
        left.addWidget(self.timeline)

        # playback row
        pb = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setFixedWidth(70)
        self.play_btn.clicked.connect(self._toggle_play)
        self.time_label = QLabel("0:00 / 0:00")
        pb.addWidget(self.play_btn)
        pb.addWidget(self.time_label)
        pb.addStretch()
        left.addLayout(pb)

        # platform row
        left.addWidget(self._section_label("Platform"))
        plat = QHBoxLayout()
        self._platform_btns: dict[str, QPushButton] = {}
        self._platform_labels: dict[str, str] = {}
        for name, label in [
            ("instagram", "Instagram"),
            ("tiktok", "TikTok"),
            ("twitter", "Twitter / X"),
            ("whatsapp", "WhatsApp"),
            ("telegram", "Telegram"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)  # noqa: FBT003
            btn.setChecked(name == self.selected_platform)
            btn.clicked.connect(
                lambda _, n=name: self._on_platform_click(n),
            )
            plat.addWidget(btn)
            self._platform_btns[name] = btn
            self._platform_labels[name] = label
        plat.addStretch()
        left.addLayout(plat)

        # quality row
        qual = QHBoxLayout()
        qual.addWidget(QLabel("Quality:"))
        self._quality_btns: dict[str, QPushButton] = {}
        for q, label in [("max", "Max"), ("optimized", "Optimized")]:
            btn = QPushButton(label)
            btn.setCheckable(True)  # noqa: FBT003
            btn.setChecked(q == self.selected_quality)
            btn.clicked.connect(
                lambda _, qq=q: self._select_quality(qq),
            )
            qual.addWidget(btn)
            self._quality_btns[q] = btn
        qual.addStretch()
        left.addLayout(qual)

        self.info_label = QLabel()
        self.info_label.setObjectName("info")
        self.info_label.setWordWrap(True)  # noqa: FBT003
        left.addWidget(self.info_label)
        self._update_info()

        # action row
        act = QHBoxLayout()
        self.render_btn = QPushButton("Render Video")
        self.render_btn.setObjectName("render")
        self.render_btn.clicked.connect(self._render)
        self.stop_btn = QPushButton("Stop Render")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.clicked.connect(self._stop_render)
        self.stop_btn.setVisible(False)  # noqa: FBT003
        self.open_btn = QPushButton("Open Video")
        self.open_btn.clicked.connect(self._open_dialog)
        act.addWidget(self.render_btn)
        act.addWidget(self.stop_btn)
        act.addWidget(self.open_btn)
        act.addStretch()
        left.addLayout(act)

        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)  # noqa: FBT003
        left.addWidget(self.status_label)

        # right panel
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._section_label("Preview (9:16)"))
        self.preview = PreviewWidget()
        self.preview.split_ratio = self.split_ratio
        right.addWidget(self.preview, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]
        pct = int(self.split_ratio * 100)
        self.split_label = QLabel(
            f"Split: {pct}% / {100 - pct}% — Drag the red bar to adjust",
        )
        self.split_label.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        self.split_label.setStyleSheet(
            "color: #888; font-size: 12px;",
        )
        right.addWidget(self.split_label)
        right.addStretch()

        root.addLayout(left, stretch=3)
        root.addLayout(right, stretch=0)

        # signals
        self.crop_widget.crops_changed.connect(self._on_crops_changed)
        self.preview.split_ratio_changed.connect(
            self._on_split_changed,
        )
        self.timeline.range_changed.connect(self._on_range_changed)
        self.timeline.seek_requested.connect(self._on_seek)

        # drop overlay (parented to central so it covers everything)
        self._drop_overlay = DropOverlay(central)
        self._drop_overlay.hide()

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    # ---- file open ----

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;All Files (*)",
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str | Path) -> None:
        """Load and display the video at *path*."""
        path = Path(path)
        if not path.exists():
            QMessageBox.warning(
                self,
                "Error",
                f"File not found:\n{path}",
            )
            return

        try:
            info = probe_video(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Error",
                f"Could not read video:\n{exc}",
            )
            return

        self.video_info = info
        self.video_info["path"] = path

        self.crop_widget.set_source_size(
            info["width"],
            info["height"],
        )
        self.crop_widget.init_crops()
        self._restore_crops()
        self.preview.source_w = info["width"]
        self.preview.source_h = info["height"]
        self.timeline.set_duration(info["duration"])
        self._update_crop_aspects()

        self._waiting_first_frame = True
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

        self.setWindowTitle(f"Trimmy — {path.name}")
        self.status_label.setText("")

    # ---- media player callbacks ----

    def _on_frame(self, frame: Any) -> None:
        img = frame.toImage()
        if img.isNull():
            return
        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
        self.current_frame = img
        self.crop_widget.set_frame(img)
        self.preview.set_frame(img)

        if self._waiting_first_frame:
            self._waiting_first_frame = False
            self.player.pause()

    def _on_position(self, ms: int) -> None:
        sec = ms / 1000.0
        self.timeline.set_position(sec)
        if self.video_info:
            self.time_label.setText(
                f"{self._fmt(sec)} / {self._fmt(self.video_info['duration'])}",
            )
            if sec >= self.timeline.trim_end:
                self.player.pause()
                self.player.setPosition(
                    int(self.timeline.trim_start * 1000),
                )
                self.play_btn.setText("Play")

    # ---- playback ----

    def _toggle_play(self) -> None:
        if not self.video_info:
            self._open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("Play")
        else:
            pos_sec = self.player.position() / 1000.0
            if pos_sec < self.timeline.trim_start or pos_sec >= self.timeline.trim_end:
                self.player.setPosition(
                    int(self.timeline.trim_start * 1000),
                )
            self.player.play()
            self.play_btn.setText("Pause")

    # ---- timeline ----

    def _on_seek(self, sec: float) -> None:
        self.player.setPosition(int(sec * 1000))

    def _on_range_changed(self, start: float, end: float) -> None:
        self._update_info()

    # ---- crops & preview ----

    def _on_crops_changed(self) -> None:
        self.preview.set_crops(
            self.crop_widget.crops["top"],
            self.crop_widget.crops["bottom"],
        )

    def _on_split_changed(self, ratio: float) -> None:
        self.split_ratio = ratio
        pct = int(ratio * 100)
        self.split_label.setText(
            f"Split: {pct}% / {100 - pct}% — Drag the red bar to adjust",
        )
        self._update_crop_aspects()

    def _update_crop_aspects(self) -> None:
        if not self.video_info:
            return
        info = PLATFORM_INFO[self.selected_platform][self.selected_quality]
        res: str = info["res"]
        out_w, out_h = (int(x) for x in res.split("x"))
        top_h = out_h * self.split_ratio
        bot_h = out_h * (1 - self.split_ratio)
        self.crop_widget.set_crop_aspects(
            out_w / top_h,
            out_w / bot_h,
        )
        self._on_crops_changed()

    # ---- platform / quality ----

    def _on_platform_click(self, name: str) -> None:
        formats = PLATFORM_FORMATS[name]
        btn = self._platform_btns[name]
        if len(formats) == 1:
            self._select_platform(name, formats[0]["key"])
            return
        btn.setChecked(name == self.selected_platform)
        menu = QMenu(self)
        for fmt in formats:
            if fmt["max_duration"] is not None:
                dur_text = self._fmt_max_duration(
                    fmt["max_duration"],
                )
                action = menu.addAction(
                    f"{fmt['label']}  (max {dur_text})",
                )
            else:
                action = menu.addAction(
                    f"{fmt['label']}  (no time limit)",
                )
            action.triggered.connect(
                lambda _, n=name, f=fmt["key"]: self._select_platform(
                    n,
                    f,
                ),
            )
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))  # ty: ignore[invalid-argument-type]

    def _select_platform(
        self,
        name: str,
        format_key: str | None = None,
    ) -> None:
        self.selected_platform = name
        if format_key is None:
            format_key = PLATFORM_FORMATS[name][0]["key"]
        self.selected_format = format_key
        for n, btn in self._platform_btns.items():
            btn.setChecked(n == name)
        self._update_crop_aspects()
        self._update_info()

    def _get_format(
        self,
        platform: str,
        format_key: str,
    ) -> dict[str, Any]:
        for fmt in PLATFORM_FORMATS[platform]:
            if fmt["key"] == format_key:
                return fmt
        return PLATFORM_FORMATS[platform][0]

    @staticmethod
    def _fmt_max_duration(seconds: int) -> str:
        if seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h" if m == 0 else f"{h}h {m}m"
        if seconds >= 60:
            m = seconds // 60
            s = seconds % 60
            return f"{m} min" if s == 0 else f"{m}m {s}s"
        return f"{seconds}s"

    def _select_quality(self, q: str) -> None:
        self.selected_quality = q
        for qq, btn in self._quality_btns.items():
            btn.setChecked(qq == q)
        self._update_crop_aspects()
        self._update_info()

    def _update_info(self) -> None:
        info = PLATFORM_INFO[self.selected_platform][self.selected_quality]
        fmt = self._get_format(
            self.selected_platform,
            self.selected_format,
        )
        fps_text = f"up to {info['maxFps']} fps"
        if self.video_info:
            src_fps = self.video_info["fps"]
            if src_fps <= info["maxFps"]:
                fps_text = f"{src_fps} fps (original)"
            else:
                fps_text = f"{info['maxFps']} fps (capped from {src_fps})"
        text = (
            f"{info['res']}  ·  {info['codec']}  ·  "
            f"{fps_text}  ·  {info['audio']}\n"
            f"{info['bitrate']}  ·  Max {info['maxSize']}"
            f"  ·  {info['note']}"
        )
        if fmt["max_duration"] is not None:
            dur_text = self._fmt_max_duration(fmt["max_duration"])
            text += f"\nFormat: {fmt['label']} (max {dur_text})"
            if self.video_info:
                trimmed_dur = self.timeline.trim_end - self.timeline.trim_start
                if trimmed_dur > fmt["max_duration"]:
                    num_parts = math.ceil(
                        trimmed_dur / fmt["max_duration"],
                    )
                    text += f"  ·  Will split into {num_parts} parts"
        else:
            text += f"\nFormat: {fmt['label']} (no time limit)"
        self.info_label.setText(text)

    # ---- render ----

    def _render(self) -> None:
        if not self.video_info:
            return
        src = self.video_info["path"]
        fmt = self._get_format(
            self.selected_platform,
            self.selected_format,
        )
        max_duration = fmt["max_duration"]

        default_name = (
            f"{src.stem}_{self.selected_platform}_{self.selected_quality}.mp4"
        )
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Rendered Video",
            str(src.parent / default_name),
            "MP4 Files (*.mp4)",
        )
        if not out_path:
            return

        self.render_btn.setEnabled(False)  # noqa: FBT003
        self.stop_btn.setVisible(True)  # noqa: FBT003
        self.status_label.setStyleSheet(
            "background: #0f3460; color: #4ecdc4;"
            " padding: 8px 12px; border-radius: 6px;",
        )
        self.status_label.setText(
            "Rendering... this may take a while",
        )

        self._render_thread = RenderThread(
            max_duration=max_duration,
            src_path=src,
            out_path=Path(out_path),
            trim_start=self.timeline.trim_start,
            trim_end=self.timeline.trim_end,
            top_crop=self.crop_widget.crops["top"],
            bottom_crop=self.crop_widget.crops["bottom"],
            split_ratio=self.split_ratio,
            platform=self.selected_platform,
            quality=self.selected_quality,
            source_fps=self.video_info["fps"],
        )
        self._render_thread.progress.connect(
            self._on_render_progress,
        )
        self._render_thread.finished.connect(
            lambda r: self._on_render_done(r, out_path),
        )
        self._render_thread.start()

    def _on_render_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self.status_label.setText(
            f"Rendering part {current} of {total}...",
        )

    def _on_render_done(  # noqa: PLR0912
        self,
        result: dict[str, Any] | list[dict[str, Any]],
        out_path: str,
    ) -> None:
        self.render_btn.setEnabled(True)  # noqa: FBT003
        self.stop_btn.setVisible(False)  # noqa: FBT003

        cancelled = (
            isinstance(result, dict) and result.get("error") == "Cancelled"
        ) or (
            isinstance(result, list)
            and any(r.get("error") == "Cancelled" for r in result)
        )
        if cancelled:
            self.status_label.setStyleSheet(
                "background: #3a3a1e; color: #e0c040;"
                " padding: 8px 12px; border-radius: 6px;",
            )
            self.status_label.setText("Render stopped.")
            return

        if isinstance(result, list):
            errors = [r for r in result if "error" in r]
            if errors:
                self.status_label.setStyleSheet(_STYLE_ERROR)
                self.status_label.setText(
                    f"Error in part {errors[0]['part']}: {errors[0]['error'][:300]}",
                )
            else:
                total_size = round(
                    sum(r["size_mb"] for r in result),
                    2,
                )
                self.status_label.setStyleSheet(_STYLE_SUCCESS)
                encoder = result[0].get("encoder", "libx264")
                self.status_label.setText(
                    f"Done! {len(result)} parts  ·  "
                    f"{result[0]['resolution']}  ·  "
                    f"{result[0]['fps']} fps  ·  "
                    f"Total {total_size} MB  ·  {encoder}",
                )
        elif "error" in result:
            self.status_label.setStyleSheet(_STYLE_ERROR)
            self.status_label.setText(
                f"Error: {result['error'][:300]}",
            )
        else:
            self.status_label.setStyleSheet(_STYLE_SUCCESS)
            encoder = result.get("encoder", "libx264")
            self.status_label.setText(
                f"Done! {result['resolution']}  ·  "
                f"{result['fps']} fps  ·  "
                f"{result['size_mb']} MB  ·  "
                f"{encoder}  ->  {out_path}",
            )

    def _stop_render(self) -> None:
        if self._render_thread is not None and self._render_thread.isRunning():
            self._render_thread.stop()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Shut down the render thread and save config on exit."""
        if self._render_thread is not None and self._render_thread.isRunning():
            self._render_thread.finished.disconnect()
            self._render_thread.stop()
            self._render_thread.wait()
        self.player.stop()
        self._save_config()
        super().closeEvent(event)

    def _save_config(self) -> None:
        top = self.crop_widget.crops["top"]
        bot = self.crop_widget.crops["bottom"]
        config.save(
            {
                "selected_platform": self.selected_platform,
                "selected_format": self.selected_format,
                "selected_quality": self.selected_quality,
                "split_ratio": self.split_ratio,
                "crops": {
                    "top": {
                        "x": top.x,
                        "y": top.y,
                        "w": top.w,
                        "h": top.h,
                    },
                    "bottom": {
                        "x": bot.x,
                        "y": bot.y,
                        "w": bot.w,
                        "h": bot.h,
                    },
                },
            },
        )

    def _restore_crops(self) -> None:
        saved = self._cfg.get("crops", {})
        tc = saved.get("top", {})
        bc = saved.get("bottom", {})
        if tc.get("w", 0) > 0 and tc.get("h", 0) > 0:
            self.crop_widget.crops["top"] = CropRect(
                tc["x"],
                tc["y"],
                tc["w"],
                tc["h"],
            )
        if bc.get("w", 0) > 0 and bc.get("h", 0) > 0:
            self.crop_widget.crops["bottom"] = CropRect(
                bc["x"],
                bc["y"],
                bc["w"],
                bc["h"],
            )

    # ---- keyboard ----

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle keyboard shortcuts for playback, trimming, and help."""
        if event.key() == Qt.Key_K:  # ty: ignore[unresolved-attribute]
            self._toggle_play()
        elif event.key() == Qt.Key_J:  # ty: ignore[unresolved-attribute]
            self.player.setPosition(
                max(0, self.player.position() - 5000),
            )
        elif event.key() == Qt.Key_L:  # ty: ignore[unresolved-attribute]
            dur = int(
                (self.video_info["duration"] if self.video_info else 0) * 1000,
            )
            self.player.setPosition(
                min(dur, self.player.position() + 5000),
            )
        elif event.key() == Qt.Key_Q:  # ty: ignore[unresolved-attribute]
            self._set_trim_start_to_playhead()
        elif event.key() == Qt.Key_E:  # ty: ignore[unresolved-attribute]
            self._set_trim_end_to_playhead()
        elif event.key() == Qt.Key_Question:  # ty: ignore[unresolved-attribute]
            self._show_keybindings_help()
        else:
            super().keyPressEvent(event)

    def _set_trim_start_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        if pos < self.timeline.trim_end - 0.1:
            self.timeline.trim_start = pos
            self.timeline.update()
            self.timeline.range_changed.emit(
                self.timeline.trim_start,
                self.timeline.trim_end,
            )

    def _set_trim_end_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        if pos > self.timeline.trim_start + 0.1:
            self.timeline.trim_end = pos
            self.timeline.update()
            self.timeline.range_changed.emit(
                self.timeline.trim_start,
                self.timeline.trim_end,
            )

    def _show_keybindings_help(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setFixedSize(360, 280)
        dialog.setStyleSheet(
            "QDialog { background: #1a1a2e; }QLabel { color: #ffffff; }"
        )
        layout = QVBoxLayout(dialog)
        layout.setSpacing(6)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        layout.addWidget(title)
        layout.addSpacing(8)

        shortcuts = [
            ("K", "Play / Pause"),
            ("J", "Seek backward 5s"),
            ("L", "Seek forward 5s"),
            ("Q", "Set trim start to playhead"),
            ("E", "Set trim end to playhead"),
            ("?", "Show this help"),
        ]
        row_font = QFont()
        row_font.setPointSize(10)
        for key, desc in shortcuts:
            row = QHBoxLayout()
            key_label = QLabel(key)
            key_label.setFont(row_font)
            key_label.setFixedWidth(100)
            key_label.setStyleSheet(
                "color: #e94560; font-weight: bold;",
            )
            desc_label = QLabel(desc)
            desc_label.setFont(row_font)
            desc_label.setStyleSheet("color: #cccccc;")
            row.addWidget(key_label)
            row.addWidget(desc_label)
            layout.addLayout(row)

        layout.addSpacing(10)
        hint = QLabel("Press Esc to close")
        hint.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        hint.setStyleSheet("color: #666666; font-size: 9pt;")
        layout.addWidget(hint)

        dialog.exec()

    # ---- drag and drop ----

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Show the drop overlay when a file is dragged in."""
        if event.mimeData().hasUrls():
            self._drop_overlay.setGeometry(
                self.centralWidget().rect(),
            )
            self._drop_overlay.show()
            self._drop_overlay.raise_()
            event.acceptProposedAction()

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        """Hide the drop overlay when the drag leaves."""
        self._drop_overlay.hide()

    @override
    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Open the first dropped video file."""
        self._drop_overlay.hide()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.open_file(path)
                break

    # ---- helpers ----

    @staticmethod
    def _fmt(s: float) -> str:
        m = int(s // 60)
        sec = int(s % 60)
        return f"{m}:{sec:02d}"


def run(file_path: str | None = None) -> None:
    """Launch the Trimmy application."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        logger.error(
            "ffmpeg and ffprobe must be installed and in PATH.",
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(file_path)
    win.show()
    sys.exit(app.exec())
