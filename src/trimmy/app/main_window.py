"""Main application window and render worker."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import (
    QCloseEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QImage,
    QKeyEvent,
)
from PySide6.QtMultimedia import (
    QAudioOutput,
    QMediaPlayer,
    QVideoFrame,
    QVideoSink,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from trimmy import __version__
from trimmy.app.components import (
    DropOverlay,
    KeybindingsDialog,
    SectionLabel,
    StatusLabel,
    ToggleButtonGroup,
    VolumeControl,
)
from trimmy.app.preferences.application.load_preferences_use_case import (
    LoadPreferencesUseCase,
)
from trimmy.app.preferences.application.save_preferences_use_case import (
    SavePreferencesUseCase,
)
from trimmy.app.preferences.domain.models import Preferences
from trimmy.app.preferences.infrastructure.json_preferences_repository import (
    JsonPreferencesRepository,
)
from trimmy.app.theme import Spacing, build_stylesheet
from trimmy.app.widgets import (
    CropWidget,
    PreviewWidget,
    TimelineWidget,
)
from trimmy.editing.crop.domain.services import AspectRatioCalculator
from trimmy.editing.shared.domain.models import CropSelection
from trimmy.editing.trim.application.set_trim_end_use_case import (
    SetTrimEndRequest,
    SetTrimEndUseCase,
)
from trimmy.editing.trim.application.set_trim_start_use_case import (
    SetTrimStartRequest,
    SetTrimStartUseCase,
)
from trimmy.rendering.application.coordinator import RenderCoordinator
from trimmy.rendering.application.plan_segments_use_case import (
    PlanSegmentsRequest,
    PlanSegmentsUseCase,
)
from trimmy.rendering.application.probe_video_use_case import (
    ProbeVideoRequest,
    ProbeVideoUseCase,
)
from trimmy.rendering.application.render_segments_use_case import (
    RenderSegmentsUseCase,
)
from trimmy.rendering.domain.messages import (
    RenderCompleted,
    RenderProgressed,
    StartRendering,
    StopRendering,
)
from trimmy.rendering.domain.models import (
    PlatformFormat,
    RenderJobResult,
    RenderSpec,
    VideoMetadata,
)
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.rendering.domain.services import FormatSelector
from trimmy.rendering.infrastructure.ffmpeg import (
    FFmpegRenderingBackend,
    FFprobeVideoProber,
)
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.domain.event_bus import EventBus
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus
from trimmy.shared.infrastructure.pyside_event_bus import PySideEventBus

logger = logging.getLogger(__name__)


class RenderWorker(QThread):
    """
    Runs the render pipeline off the GUI thread, bridging events to *bus*.

    The blocking work is driven by the same :class:`RenderCoordinator` the
    rendering context uses everywhere: the worker owns a private synchronous
    bus, lets the coordinator handle the ``StartRendering`` command on this
    thread, and forwards the resulting events onto the GUI bus (whose queued
    Qt signal hops them back to the GUI thread).
    """

    def __init__(
        self,
        bus: EventBus,
        presets: PresetRepository,
        command: StartRendering,
    ) -> None:
        super().__init__()
        self._bus = bus
        self._presets = presets
        self._command = command
        self._backend = FFmpegRenderingBackend()

    def stop(self) -> None:
        """Request cancellation of the running render."""
        self._backend.cancel()

    @override
    def run(self) -> None:  # noqa: D102
        local = InMemoryEventBus()
        use_case = RenderSegmentsUseCase(self._presets, self._backend)
        RenderCoordinator(local, use_case, self._backend)
        local.subscribe(RenderProgressed, self._bus.publish)
        local.subscribe(RenderCompleted, self._bus.publish)
        local.publish(self._command)


class MainWindow(QMainWindow):
    """Primary application window with crop, preview, and render controls."""

    def __init__(self, file_path: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Trimmy")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(build_stylesheet())

        self.setAcceptDrops(True)  # noqa: FBT003

        self._presets = InMemoryPresetRepository()
        self._format_selector = FormatSelector()
        self._aspect_calculator = AspectRatioCalculator()
        self._probe = ProbeVideoUseCase(FFprobeVideoProber())
        self._plan_segments = PlanSegmentsUseCase()
        self._prefs_repository = JsonPreferencesRepository()

        self.video_info: VideoMetadata | None = None
        self._source_path: Path | None = None
        self.current_frame: QImage | None = None

        self._prefs = LoadPreferencesUseCase(self._prefs_repository).load()
        self.selected_platform: str = self._prefs.selected_platform
        self.selected_format: str = self._prefs.selected_format
        self.selected_quality: str = self._prefs.selected_quality
        self.split_ratio: float = self._prefs.split_ratio
        self._waiting_first_frame: bool = False

        self._bus = PySideEventBus(self)
        self._bus.subscribe(StartRendering, self._on_start_rendering)
        self._bus.subscribe(StopRendering, self._on_stop_rendering)
        self._bus.subscribe(RenderProgressed, self._on_render_progressed)
        self._bus.subscribe(RenderCompleted, self._on_render_completed)
        self._render_worker: RenderWorker | None = None
        self._render_out_path: str | None = None

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self._volume = self._prefs.volume
        self.audio.setVolume(self._volume / 100.0)
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
        root.setSpacing(Spacing.MD)
        root.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        left = QVBoxLayout()
        left.setSpacing(Spacing.SM)

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

        self.volume_control = VolumeControl(initial_volume=self._volume)
        self.volume_control.volume_changed.connect(self._on_volume_changed)
        pb.addWidget(self.volume_control)

        left.addLayout(pb)

        # platform row
        left.addWidget(SectionLabel("Platform"))
        self._platform_group = ToggleButtonGroup(
            options=[
                ("instagram", "Instagram"),
                ("tiktok", "TikTok"),
                ("twitter", "Twitter / X"),
                ("whatsapp", "WhatsApp"),
                ("telegram", "Telegram"),
            ],
            selected=self.selected_platform,
        )
        self._platform_group.selection_changed.connect(self._on_platform_click)
        left.addWidget(self._platform_group)

        # quality row
        qual = QHBoxLayout()
        qual.addWidget(QLabel("Quality:"))
        self._quality_group = ToggleButtonGroup(
            options=[("max", "Max"), ("optimized", "Optimized")],
            selected=self.selected_quality,
        )
        self._quality_group.selection_changed.connect(self._select_quality)
        qual.addWidget(self._quality_group)
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

        self.status_label = StatusLabel()
        left.addWidget(self.status_label)

        # right panel
        right = QVBoxLayout()
        right.setSpacing(Spacing.SM)
        right.addWidget(SectionLabel("Preview (9:16)"))
        self.preview = PreviewWidget()
        self.preview.split_ratio = self.split_ratio
        right.addWidget(self.preview, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]
        pct = int(self.split_ratio * 100)
        self.split_label = QLabel(
            f"Split: {pct}% / {100 - pct}% — Drag the red bar to adjust",
        )
        self.split_label.setAlignment(Qt.AlignCenter)  # ty: ignore[unresolved-attribute]
        self.split_label.setObjectName("info")
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

        # footer status bar with the app version floated to the right
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("version")
        status_bar.addPermanentWidget(self.version_label)

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
            info = self._probe.probe(ProbeVideoRequest(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "Error",
                f"Could not read video:\n{exc}",
            )
            return

        self.video_info = info
        self._source_path = path

        self.crop_widget.set_source_size(info.width, info.height)
        self.crop_widget.init_crops()
        self._restore_crops()
        self.timeline.set_duration(info.duration)
        self._update_crop_aspects()

        self._waiting_first_frame = True
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

        self.setWindowTitle(f"Trimmy — {path.name}")
        self.status_label.clear()

    # ---- media player callbacks ----

    def _on_frame(self, frame: QVideoFrame) -> None:
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
                f"{self._fmt(sec)} / {self._fmt(self.video_info.duration)}",
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

    # ---- volume ----

    def _on_volume_changed(self, value: int) -> None:
        self._volume = value
        self.audio.setVolume(value / 100.0)

    # ---- timeline ----

    def _on_seek(self, sec: float) -> None:
        self.player.setPosition(int(sec * 1000))

    def _on_range_changed(self, start: float, end: float) -> None:
        self._update_info()

    # ---- crops & preview ----

    def _on_crops_changed(self) -> None:
        self.preview.set_selection(self.crop_widget.selection)

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
        info = self._presets.display_info(
            self.selected_platform,
            self.selected_quality,
        )
        out_w, out_h = (int(x) for x in info.res.split("x"))
        aspects = self._aspect_calculator.calculate(
            out_w,
            out_h,
            self.split_ratio,
        )
        self.crop_widget.set_crop_aspects(aspects.top, aspects.bottom)
        self._on_crops_changed()

    # ---- platform / quality ----

    def _on_platform_click(self, name: str) -> None:
        formats = self._presets.formats(name)
        if len(formats) == 1:
            self._select_platform(name, formats[0].key)
            return
        btn = self._platform_group.button(name)
        btn.setChecked(name == self.selected_platform)
        menu = QMenu(self)
        for fmt in formats:
            if fmt.max_duration is not None:
                dur_text = self._fmt_max_duration(fmt.max_duration)
                action = menu.addAction(
                    f"{fmt.label}  (max {dur_text})",
                )
            else:
                action = menu.addAction(
                    f"{fmt.label}  (no time limit)",
                )
            action.triggered.connect(
                lambda _, n=name, f=fmt.key: self._select_platform(n, f),
            )
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))  # ty: ignore[invalid-argument-type]

    def _select_platform(
        self,
        name: str,
        format_key: str | None = None,
    ) -> None:
        self.selected_platform = name
        if format_key is None:
            format_key = self._presets.formats(name)[0].key
        self.selected_format = format_key
        self._platform_group.set_selected(name)
        self._update_crop_aspects()
        self._update_info()

    def _get_format(self, platform: str, format_key: str) -> PlatformFormat:
        return self._format_selector.select(
            self._presets.formats(platform),
            format_key,
        )

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
        self._quality_group.set_selected(q)
        self._update_crop_aspects()
        self._update_info()

    def _update_info(self) -> None:
        info = self._presets.display_info(
            self.selected_platform,
            self.selected_quality,
        )
        fmt = self._get_format(self.selected_platform, self.selected_format)
        fps_text = f"up to {info.max_fps} fps"
        if self.video_info:
            src_fps = self.video_info.fps
            if src_fps <= info.max_fps:
                fps_text = f"{src_fps} fps (original)"
            else:
                fps_text = f"{info.max_fps} fps (capped from {src_fps})"
        text = (
            f"{info.res}  ·  {info.codec}  ·  "
            f"{fps_text}  ·  {info.audio}\n"
            f"{info.bitrate}  ·  Max {info.max_size}"
            f"  ·  {info.note}"
        )
        if fmt.max_duration is not None:
            dur_text = self._fmt_max_duration(fmt.max_duration)
            text += f"\nFormat: {fmt.label} (max {dur_text})"
            if self.video_info:
                segments = self._plan_segments.plan(
                    PlanSegmentsRequest(
                        self.timeline.trim_range,
                        fmt.max_duration,
                    ),
                )
                if len(segments) > 1:
                    text += f"  ·  Will split into {len(segments)} parts"
        else:
            text += f"\nFormat: {fmt.label} (no time limit)"
        self.info_label.setText(text)

    # ---- render ----

    def _render(self) -> None:
        if not self.video_info or self._source_path is None:
            return
        src = self._source_path
        fmt = self._get_format(self.selected_platform, self.selected_format)
        max_duration = fmt.max_duration

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
        self.status_label.set_info(
            "Rendering... this may take a while",
        )

        spec = RenderSpec(
            source_path=src,
            output_path=Path(out_path),
            trim=self.timeline.trim_range,
            crops=self.crop_widget.selection,
            split_ratio=self.split_ratio,
            platform=self.selected_platform,
            quality=self.selected_quality,
            source_fps=self.video_info.fps,
        )
        self._render_out_path = out_path
        self._bus.publish(StartRendering(spec, max_duration))

    def _on_start_rendering(self, command: StartRendering) -> None:
        """Launch the render worker for *command* off the GUI thread."""
        self._render_worker = RenderWorker(self._bus, self._presets, command)
        self._render_worker.start()

    def _on_stop_rendering(self, _command: StopRendering) -> None:
        """Cancel the in-flight render, if any."""
        if self._render_worker is not None and self._render_worker.isRunning():
            self._render_worker.stop()

    def _on_render_progressed(self, event: RenderProgressed) -> None:
        self.status_label.set_info(
            f"Rendering part {event.current} of {event.total}...",
        )

    def _on_render_completed(self, event: RenderCompleted) -> None:
        result = event.result
        out_path = self._render_out_path or ""
        self.render_btn.setEnabled(True)  # noqa: FBT003
        self.stop_btn.setVisible(False)  # noqa: FBT003

        if result.is_cancelled:
            self.status_label.set_warning("Render stopped.")
            return

        if result.multipart:
            self._show_multipart_result(result)
            return

        outcome = result.first
        if outcome.is_failed:
            self.status_label.set_error(f"Error: {(outcome.error or '')[:300]}")
            return
        self.status_label.set_success(
            f"Done! {outcome.resolution}  ·  "
            f"{outcome.fps} fps  ·  "
            f"{outcome.size_mb} MB  ·  "
            f"{outcome.encoder}  ->  {out_path}",
        )

    def _show_multipart_result(self, result: RenderJobResult) -> None:
        failures = result.failures
        if failures:
            first = failures[0]
            self.status_label.set_error(
                f"Error in part {first.index}: {(first.error or '')[:300]}",
            )
            return
        first = result.first
        self.status_label.set_success(
            f"Done! {result.parts} parts  ·  "
            f"{first.resolution}  ·  "
            f"{first.fps} fps  ·  "
            f"Total {result.total_size_mb} MB  ·  {first.encoder}",
        )

    def _stop_render(self) -> None:
        self._bus.publish(StopRendering())

    @override
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Shut down the render worker and save config on exit."""
        if self._render_worker is not None and self._render_worker.isRunning():
            self._render_worker.stop()
            self._render_worker.wait()
        self.player.stop()
        self._save_config()
        super().closeEvent(event)

    def _save_config(self) -> None:
        preferences = Preferences(
            selected_platform=self.selected_platform,
            selected_format=self.selected_format,
            selected_quality=self.selected_quality,
            split_ratio=self.split_ratio,
            volume=self._volume,
            crops=self.crop_widget.selection,
        )
        SavePreferencesUseCase(self._prefs_repository).save(preferences)

    def _restore_crops(self) -> None:
        saved = self._prefs.crops
        current = self.crop_widget.selection
        top = saved.top if not saved.top.is_empty else current.top
        bottom = saved.bottom if not saved.bottom.is_empty else current.bottom
        self.crop_widget.set_selection(CropSelection(top=top, bottom=bottom))

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
                (self.video_info.duration if self.video_info else 0) * 1000,
            )
            self.player.setPosition(
                min(dur, self.player.position() + 5000),
            )
        elif event.key() == Qt.Key_Q:  # ty: ignore[unresolved-attribute]
            self._set_trim_start_to_playhead()
        elif event.key() == Qt.Key_E:  # ty: ignore[unresolved-attribute]
            self._set_trim_end_to_playhead()
        elif event.key() == Qt.Key_M:  # ty: ignore[unresolved-attribute]
            self.volume_control.toggle_mute()
        elif event.key() == Qt.Key_Question:  # ty: ignore[unresolved-attribute]
            self._show_keybindings_help()
        else:
            super().keyPressEvent(event)

    def _set_trim_start_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        updated = SetTrimStartUseCase().set_start(
            SetTrimStartRequest(self.timeline.trim_range, pos),
        )
        self.timeline.apply_range(updated)

    def _set_trim_end_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        updated = SetTrimEndUseCase().set_end(
            SetTrimEndRequest(
                self.timeline.trim_range,
                pos,
                self.video_info.duration,
            ),
        )
        self.timeline.apply_range(updated)

    def _show_keybindings_help(self) -> None:
        shortcuts = [
            ("K", "Play / Pause"),
            ("J", "Seek backward 5s"),
            ("L", "Seek forward 5s"),
            ("Q", "Set trim start to playhead"),
            ("E", "Set trim end to playhead"),
            ("M", "Toggle mute"),
            ("?", "Show this help"),
        ]
        dialog = KeybindingsDialog(shortcuts, self)
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
