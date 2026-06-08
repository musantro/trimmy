import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink, QAudioOutput
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QSizePolicy,
)

from PySide6.QtGui import QImage, QPainter, QFont, QColor, QPen

from video_trimmer.presets import PLATFORM_PRESETS, PLATFORM_INFO
from video_trimmer.renderer import probe_video, render_video, CropRect
from video_trimmer.widgets import CropWidget, PreviewWidget, TimelineWidget


class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(10, 10, 30, 200))

        border = QColor("#e94560")
        pen = QPen(border, 3, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        margin = 40
        p.drawRoundedRect(
            margin, margin,
            self.width() - 2 * margin, self.height() - 2 * margin,
            16, 16,
        )

        p.setPen(QColor("#e94560"))
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignCenter, "Drop video here")

    def resizeEvent(self, event):
        super().resizeEvent(event)

STYLESHEET = """
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
QLabel#section { color: #aaa; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
QLabel#status { padding: 8px 12px; border-radius: 6px; font-size: 13px; }
QLabel#info { color: #888; font-size: 12px; }
"""


class RenderThread(QThread):
    finished = Signal(dict)

    def __init__(self, **kwargs):
        super().__init__()
        self._kwargs = kwargs

    def run(self):
        result = render_video(**self._kwargs)
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self, file_path=None):
        super().__init__()
        self.setWindowTitle("Trimmy")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(STYLESHEET)

        self.setAcceptDrops(True)

        self.video_info = None
        self.current_frame = None
        self.selected_platform = "instagram"
        self.selected_quality = "max"
        self.split_ratio = 0.5
        self._waiting_first_frame = False
        self._render_thread = None

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.audio.setMuted(True)
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink()
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.player.positionChanged.connect(self._on_position)

        self._build_ui()

        if file_path:
            self.open_file(file_path)

    def _build_ui(self):
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
        self._platform_btns = {}
        for name, label in [
            ("instagram", "Instagram"),
            ("tiktok", "TikTok"),
            ("twitter", "Twitter / X"),
            ("whatsapp", "WhatsApp"),
            ("telegram", "Telegram"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(name == self.selected_platform)
            btn.clicked.connect(lambda _, n=name: self._select_platform(n))
            plat.addWidget(btn)
            self._platform_btns[name] = btn
        plat.addStretch()
        left.addLayout(plat)

        # quality row
        qual = QHBoxLayout()
        qual.addWidget(QLabel("Quality:"))
        self._quality_btns = {}
        for q, label in [("max", "Max"), ("optimized", "Optimized")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(q == self.selected_quality)
            btn.clicked.connect(lambda _, qq=q: self._select_quality(qq))
            qual.addWidget(btn)
            self._quality_btns[q] = btn
        qual.addStretch()
        left.addLayout(qual)

        self.info_label = QLabel()
        self.info_label.setObjectName("info")
        self.info_label.setWordWrap(True)
        left.addWidget(self.info_label)
        self._update_info()

        # action row
        act = QHBoxLayout()
        self.render_btn = QPushButton("Render Video")
        self.render_btn.setObjectName("render")
        self.render_btn.clicked.connect(self._render)
        self.open_btn = QPushButton("Open Video")
        self.open_btn.clicked.connect(self._open_dialog)
        act.addWidget(self.render_btn)
        act.addWidget(self.open_btn)
        act.addStretch()
        left.addLayout(act)

        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        # right panel
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._section_label("Preview (9:16)"))
        self.preview = PreviewWidget()
        right.addWidget(self.preview, alignment=Qt.AlignHCenter)
        self.split_label = QLabel("Split: 50% / 50% — Drag the red bar to adjust")
        self.split_label.setAlignment(Qt.AlignCenter)
        self.split_label.setStyleSheet("color: #888; font-size: 12px;")
        right.addWidget(self.split_label)
        right.addStretch()

        root.addLayout(left, stretch=3)
        root.addLayout(right, stretch=0)

        # signals
        self.crop_widget.crops_changed.connect(self._on_crops_changed)
        self.preview.split_ratio_changed.connect(self._on_split_changed)
        self.timeline.range_changed.connect(self._on_range_changed)
        self.timeline.seek_requested.connect(self._on_seek)

        # drop overlay (parented to central so it covers everything)
        self._drop_overlay = DropOverlay(central)
        self._drop_overlay.hide()

    @staticmethod
    def _section_label(text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    # ---- file open ----

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm);;All Files (*)",
        )
        if path:
            self.open_file(path)

    def open_file(self, path):
        path = Path(path)
        if not path.exists():
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            return

        try:
            info = probe_video(path)
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Could not read video:\n{exc}")
            return

        self.video_info = info
        self.video_info["path"] = path

        self.crop_widget.set_source_size(info["width"], info["height"])
        self.crop_widget.init_crops()
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

    def _on_frame(self, frame):
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

    def _on_position(self, ms):
        sec = ms / 1000.0
        self.timeline.set_position(sec)
        if self.video_info:
            self.time_label.setText(
                f"{self._fmt(sec)} / {self._fmt(self.video_info['duration'])}"
            )
            if sec >= self.timeline.trim_end:
                self.player.pause()
                self.player.setPosition(int(self.timeline.trim_start * 1000))
                self.play_btn.setText("Play")

    # ---- playback ----

    def _toggle_play(self):
        if not self.video_info:
            self._open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_btn.setText("Play")
        else:
            pos_sec = self.player.position() / 1000.0
            if pos_sec < self.timeline.trim_start or pos_sec >= self.timeline.trim_end:
                self.player.setPosition(int(self.timeline.trim_start * 1000))
            self.player.play()
            self.play_btn.setText("Pause")

    # ---- timeline ----

    def _on_seek(self, sec):
        self.player.setPosition(int(sec * 1000))

    def _on_range_changed(self, start, end):
        pass

    # ---- crops & preview ----

    def _on_crops_changed(self):
        self.preview.set_crops(self.crop_widget.crops["top"], self.crop_widget.crops["bottom"])

    def _on_split_changed(self, ratio):
        self.split_ratio = ratio
        pct = int(ratio * 100)
        self.split_label.setText(f"Split: {pct}% / {100 - pct}% — Drag the red bar to adjust")
        self._update_crop_aspects()

    def _update_crop_aspects(self):
        if not self.video_info:
            return
        info = PLATFORM_INFO[self.selected_platform][self.selected_quality]
        out_w, out_h = (int(x) for x in info["res"].split("x"))
        top_h = out_h * self.split_ratio
        bot_h = out_h * (1 - self.split_ratio)
        self.crop_widget.set_crop_aspects(out_w / top_h, out_w / bot_h)
        self._on_crops_changed()

    # ---- platform / quality ----

    def _select_platform(self, name):
        self.selected_platform = name
        for n, btn in self._platform_btns.items():
            btn.setChecked(n == name)
        self._update_crop_aspects()
        self._update_info()

    def _select_quality(self, q):
        self.selected_quality = q
        for qq, btn in self._quality_btns.items():
            btn.setChecked(qq == q)
        self._update_crop_aspects()
        self._update_info()

    def _update_info(self):
        info = PLATFORM_INFO[self.selected_platform][self.selected_quality]
        fps_text = f"up to {info['maxFps']} fps"
        if self.video_info:
            src_fps = self.video_info["fps"]
            if src_fps <= info["maxFps"]:
                fps_text = f"{src_fps} fps (original)"
            else:
                fps_text = f"{info['maxFps']} fps (capped from {src_fps})"
        self.info_label.setText(
            f"{info['res']}  ·  {info['codec']}  ·  {fps_text}  ·  {info['audio']}\n"
            f"{info['bitrate']}  ·  Max {info['maxSize']}  ·  {info['note']}"
        )

    # ---- render ----

    def _render(self):
        if not self.video_info:
            return
        src = self.video_info["path"]
        default_name = f"{src.stem}_{self.selected_platform}_{self.selected_quality}.mp4"
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Rendered Video",
            str(src.parent / default_name),
            "MP4 Files (*.mp4)",
        )
        if not out_path:
            return

        self.render_btn.setEnabled(False)
        self.status_label.setStyleSheet("background: #0f3460; color: #4ecdc4; padding: 8px 12px; border-radius: 6px;")
        self.status_label.setText("Rendering... this may take a while")

        self._render_thread = RenderThread(
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
        self._render_thread.finished.connect(lambda r: self._on_render_done(r, out_path))
        self._render_thread.start()

    def _on_render_done(self, result, out_path):
        self.render_btn.setEnabled(True)
        if "error" in result:
            self.status_label.setStyleSheet("background: #4a1a1a; color: #e94560; padding: 8px 12px; border-radius: 6px;")
            self.status_label.setText(f"Error: {result['error'][:300]}")
        else:
            self.status_label.setStyleSheet("background: #1a4a2e; color: #4ecdc4; padding: 8px 12px; border-radius: 6px;")
            self.status_label.setText(
                f"Done! {result['resolution']}  ·  {result['fps']} fps  ·  "
                f"{result['size_mb']} MB  →  {out_path}"
            )

    # ---- keyboard ----

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._toggle_play()
        elif event.key() == Qt.Key_Left:
            self.player.setPosition(max(0, self.player.position() - 5000))
        elif event.key() == Qt.Key_Right:
            dur = int((self.video_info["duration"] if self.video_info else 0) * 1000)
            self.player.setPosition(min(dur, self.player.position() + 5000))
        else:
            super().keyPressEvent(event)

    # ---- drag and drop ----

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self._drop_overlay.setGeometry(self.centralWidget().rect())
            self._drop_overlay.show()
            self._drop_overlay.raise_()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop_overlay.hide()

    def dropEvent(self, event):
        self._drop_overlay.hide()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.open_file(path)
                break

    # ---- helpers ----

    @staticmethod
    def _fmt(s):
        m = int(s // 60)
        sec = int(s % 60)
        return f"{m}:{sec:02d}"


def run(file_path=None):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("Error: ffmpeg and ffprobe must be installed and in PATH.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(file_path)
    win.show()
    sys.exit(app.exec())
