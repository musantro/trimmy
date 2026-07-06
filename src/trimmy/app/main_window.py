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
    QFont,
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
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from trimmy import __version__
from trimmy.app.components import (
    DropOverlay,
    KeybindingsDialog,
    SidebarNavigation,
    TopNavBar,
)
from trimmy.app.preferences.application.load_preferences_use_case import (
    LoadPreferencesUseCase,
)
from trimmy.app.preferences.application.save_preferences_use_case import (
    SavePreferencesUseCase,
)
from trimmy.app.preferences.domain.models import Preferences, TargetPreference
from trimmy.app.preferences.infrastructure.json_preferences_repository import (
    JsonPreferencesRepository,
)
from trimmy.app.theme import Typography, build_stylesheet, load_fonts
from trimmy.app.views.editor_view import EditorView
from trimmy.app.views.render_view import RenderView
from trimmy.app.views.startup_view import StartupView
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
    RenderQueueCompleted,
    RenderQueueProgressed,
    StartRendering,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import (
    PlatformFormat,
    RenderJobResult,
    RenderQueueItem,
    RenderQueueResult,
    RenderSpec,
    RenderTarget,
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

_VIEW_STARTUP = 0
_VIEW_EDITOR = 1
_VIEW_RENDER = 2


class RenderWorker(QThread):
    """Runs the render pipeline off the GUI thread, bridging events to *bus*."""

    def __init__(
        self,
        bus: EventBus,
        presets: PresetRepository,
        command: StartRendering | StartRenderQueue,
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
    def run(self) -> None:
        local = InMemoryEventBus()
        use_case = RenderSegmentsUseCase(self._presets, self._backend)
        RenderCoordinator(local, use_case, self._backend)
        local.subscribe(RenderProgressed, self._bus.publish)
        local.subscribe(RenderCompleted, self._bus.publish)
        local.subscribe(RenderQueueProgressed, self._bus.publish)
        local.subscribe(RenderQueueCompleted, self._bus.publish)
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
        self._prefs_repository = JsonPreferencesRepository()

        self.video_info: VideoMetadata | None = None
        self._source_path: Path | None = None
        self.current_frame: QImage | None = None

        self._prefs = LoadPreferencesUseCase(self._prefs_repository).load()
        self.selected_platform: str = self._prefs.selected_platform
        self.selected_format: str = self._prefs.selected_format
        self.selected_quality: str = self._prefs.selected_quality
        self.selected_targets: tuple[tuple[str, str], ...] = tuple(
            (target.platform, target.format_key)
            for target in self._prefs.selected_targets
        ) or ((self.selected_platform, self.selected_format),)
        self.split_ratio: float = self._prefs.split_ratio
        self._waiting_first_frame: bool = False

        self._bus = PySideEventBus(self)
        self._bus.subscribe(StartRendering, self._on_start_rendering)
        self._bus.subscribe(StartRenderQueue, self._on_start_rendering)
        self._bus.subscribe(StopRendering, self._on_stop_rendering)
        self._bus.subscribe(RenderProgressed, self._on_render_progressed)
        self._bus.subscribe(RenderCompleted, self._on_render_completed)
        self._bus.subscribe(RenderQueueProgressed, self._on_render_queue_progressed)
        self._bus.subscribe(RenderQueueCompleted, self._on_render_queue_completed)
        self._render_worker: RenderWorker | None = None
        self._render_out_path: str | None = None
        self._preview_player: QMediaPlayer | None = None
        self._preview_audio: QAudioOutput | None = None
        self._preview_sink: QVideoSink | None = None

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

        self._editor_view.platform_selector.blockSignals(True)  # noqa: FBT003
        self._editor_view.platform_selector.set_platform(self.selected_platform)
        if self.selected_format:
            self._editor_view.platform_selector.set_format(
                self.selected_platform,
                self.selected_format,
            )
        self._editor_view.platform_selector.set_targets(self.selected_targets)
        self._editor_view.platform_selector.blockSignals(False)  # noqa: FBT003
        self.selected_targets = self._editor_view.platform_selector.selected_targets()
        self._editor_view.render_btn.setEnabled(bool(self.selected_targets))

        if file_path:
            self.open_file(file_path)

    # ---- UI construction ----

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top navigation bar
        self._top_nav = TopNavBar(version_text=f"v{__version__}")
        self._top_nav.help_clicked.connect(self._show_keybindings_help)
        root.addWidget(self._top_nav)

        # Body: sidebar + stacked views
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = SidebarNavigation()
        self._sidebar.nav_changed.connect(self._on_nav_changed)
        self._sidebar.shortcuts_requested.connect(self._show_keybindings_help)
        self._sidebar.hide()
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()

        # Index 0: Startup view
        self._startup_view = StartupView()
        self._startup_view.open_requested.connect(self._open_dialog)
        self._stack.addWidget(self._startup_view)

        # Index 1: Editor view
        self._editor_view = EditorView()
        self._editor_view.crop_widget.crops_changed.connect(self._on_crops_changed)
        self._editor_view.preview.split_ratio_changed.connect(self._on_split_changed)
        self._editor_view.preview.split_ratio = self.split_ratio
        self._editor_view.timeline.range_changed.connect(self._on_range_changed)
        self._editor_view.timeline.seek_requested.connect(self._on_seek)
        self._editor_view.playback.play_clicked.connect(self._toggle_play)
        self._editor_view.playback.skip_prev_clicked.connect(
            lambda: self.player.setPosition(max(0, self.player.position() - 5000)),
        )
        self._editor_view.playback.skip_next_clicked.connect(
            lambda: self.player.setPosition(
                min(
                    int((self.video_info.duration if self.video_info else 0) * 1000),
                    self.player.position() + 5000,
                ),
            ),
        )
        self._editor_view.volume_control.volume_changed.connect(self._on_volume_changed)
        self._editor_view.volume_control.set_volume(self._volume)
        self._editor_view.render_btn.clicked.connect(self._render)
        self._editor_view.stop_btn.clicked.connect(self._stop_render)
        self._editor_view.platform_selector.platform_changed.connect(
            self._on_platform_changed,
        )
        self._editor_view.platform_selector.format_changed.connect(
            self._on_format_changed,
        )
        self._editor_view.platform_selector.selection_changed.connect(
            self._on_target_selection_changed,
        )
        self._stack.addWidget(self._editor_view)

        # Index 2: Render view
        self._render_view = RenderView()
        self._render_view.cancel_requested.connect(self._stop_render)
        self._render_view.done_requested.connect(self._on_render_done)
        self._stack.addWidget(self._render_view)

        self._stack.setCurrentIndex(_VIEW_STARTUP)
        body.addWidget(self._stack)

        root.addLayout(body)

        # Drop overlay parented to the stacked widget
        self._drop_overlay = DropOverlay(self._stack)
        self._drop_overlay.hide()

    # ---- navigation ----

    def _on_nav_changed(self, name: str) -> None:
        if name == "open":
            if not self.video_info:
                self._switch_to_view(_VIEW_STARTUP)
            else:
                self._open_dialog()
        elif name == "edit":
            if self.video_info:
                self._switch_to_view(_VIEW_EDITOR)
            else:
                self._switch_to_view(_VIEW_STARTUP)
        elif name == "render":
            if self._render_worker is not None and self._render_worker.isRunning():
                self._switch_to_view(_VIEW_RENDER)
            else:
                self._sidebar.set_active("edit" if self.video_info else "open")

    def _switch_to_view(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if index == _VIEW_STARTUP:
            self._sidebar.hide()
        else:
            self._sidebar.show()
            if index == _VIEW_EDITOR:
                self._sidebar.set_active("edit")
            elif index == _VIEW_RENDER:
                self._sidebar.set_active("render")

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

        self._editor_view.crop_widget.set_source_size(info.width, info.height)
        self._editor_view.crop_widget.init_crops()
        self._restore_crops()
        self._editor_view.timeline.set_duration(info.duration)
        self._update_crop_aspects()

        self._waiting_first_frame = True
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

        self.setWindowTitle(f"Trimmy — {path.name}")

        self._switch_to_view(_VIEW_EDITOR)
        self._sidebar.set_active("edit")

    # ---- media player callbacks ----

    def _on_frame(self, frame: QVideoFrame) -> None:
        img = frame.toImage()
        if img.isNull():
            return
        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
        self.current_frame = img
        self._editor_view.crop_widget.set_frame(img)
        self._editor_view.preview.set_frame(img)

        if self._waiting_first_frame:
            self._waiting_first_frame = False
            self.player.pause()

    def _on_position(self, ms: int) -> None:
        sec = ms / 1000.0
        self._editor_view.timeline.set_position(sec)
        if (
            self.video_info
            and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            and sec >= self._editor_view.timeline.trim_end
        ):
            self.player.pause()
            self.player.setPosition(
                int(self._editor_view.timeline.trim_start * 1000),
            )
            self._editor_view.playback.set_playing(playing=False)

    # ---- playback ----

    def _toggle_play(self) -> None:
        if not self.video_info:
            self._open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._editor_view.playback.set_playing(playing=False)
        else:
            pos_sec = self.player.position() / 1000.0
            if (
                pos_sec < self._editor_view.timeline.trim_start
                or pos_sec >= self._editor_view.timeline.trim_end
            ):
                self.player.setPosition(
                    int(self._editor_view.timeline.trim_start * 1000),
                )
            self.player.play()
            self._editor_view.playback.set_playing(playing=True)

    # ---- volume ----

    def _on_volume_changed(self, value: int) -> None:
        self._volume = value
        self.audio.setVolume(value / 100.0)

    # ---- timeline ----

    def _on_seek(self, sec: float) -> None:
        self.player.setPosition(int(sec * 1000))

    def _on_range_changed(self, start: float, end: float) -> None:
        pass

    # ---- crops & preview ----

    def _on_crops_changed(self) -> None:
        self._editor_view.preview.set_selection(self._editor_view.crop_widget.selection)

    def _on_split_changed(self, ratio: float) -> None:
        self.split_ratio = ratio
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
        self._editor_view.crop_widget.set_crop_aspects(aspects.top, aspects.bottom)
        self._on_crops_changed()

    # ---- platform / format ----

    def _on_platform_changed(self, name: str) -> None:
        self.selected_platform = name
        formats = self._presets.formats(name)
        if formats:
            self.selected_format = formats[0].key
        self._update_crop_aspects()

    def _on_format_changed(self, platform: str, format_key: str) -> None:
        self.selected_platform = platform
        self.selected_format = format_key
        self._update_crop_aspects()

    def _on_target_selection_changed(self) -> None:
        self.selected_targets = self._editor_view.platform_selector.selected_targets()
        self._editor_view.render_btn.setEnabled(bool(self.selected_targets))

    def _get_format(self, platform: str, format_key: str) -> PlatformFormat:
        return self._format_selector.select(
            self._presets.formats(platform),
            format_key,
        )

    # ---- render ----

    def _render(self) -> None:
        if not self.video_info or self._source_path is None:
            return
        src = self._source_path
        targets = self._editor_view.platform_selector.selected_targets()
        if not targets:
            return

        if len(targets) == 1:
            platform, format_key = targets[0]
            default_name = (
                f"{src.stem}_{platform}_{format_key}_{self.selected_quality}.mp4"
            )
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Rendered Video",
                str(src.parent / default_name),
                "MP4 Files (*.mp4)",
            )
            if not out_path:
                return
            output_paths = {targets[0]: Path(out_path)}
        else:
            out_dir = QFileDialog.getExistingDirectory(
                self,
                "Choose Render Output Folder",
                str(src.parent),
            )
            if not out_dir:
                return
            output_root = Path(out_dir)
            output_paths = {
                target: output_root
                / f"{src.stem}_{target[0]}_{target[1]}_{self.selected_quality}.mp4"
                for target in targets
            }

        self._editor_view.render_btn.setEnabled(False)
        self._editor_view.stop_btn.setVisible(True)

        items: list[RenderQueueItem] = []
        for platform, format_key in targets:
            fmt = self._get_format(platform, format_key)
            target = RenderTarget(platform, format_key, self.selected_quality)
            spec = RenderSpec(
                source_path=src,
                output_path=output_paths[(platform, format_key)],
                trim=self._editor_view.timeline.trim_range,
                crops=self._editor_view.crop_widget.selection,
                split_ratio=self.split_ratio,
                platform=platform,
                quality=self.selected_quality,
                source_fps=self.video_info.fps,
            )
            items.append(RenderQueueItem(target, spec, fmt.max_duration))
            self._render_view.set_platform_info(self._target_label(target), 0)

        self._render_out_path = str(next(iter(output_paths.values())))
        self._bus.publish(StartRenderQueue(tuple(items)))

        self._switch_to_view(_VIEW_RENDER)
        self._start_render_preview()

    def _on_start_rendering(self, command: StartRendering | StartRenderQueue) -> None:
        """Launch the render worker for *command* off the GUI thread."""
        self._render_worker = RenderWorker(self._bus, self._presets, command)
        self._render_worker.start()

    def _on_stop_rendering(self, _command: StopRendering) -> None:
        """Cancel the in-flight render, if any."""
        if self._render_worker is not None and self._render_worker.isRunning():
            self._render_worker.stop()

    def _on_render_progressed(self, event: RenderProgressed) -> None:
        self._render_view.set_global_progress(event.pct, "--:-- remaining")
        self._render_view.set_platform_info(self.selected_platform, event.pct)

    def _on_render_queue_progressed(self, event: RenderQueueProgressed) -> None:
        self._render_view.set_global_progress(event.global_pct, "--:-- remaining")
        self._render_view.set_platform_info(
            self._target_label(event.target),
            event.target_pct,
        )

    def _on_render_completed(self, event: RenderCompleted) -> None:
        result = event.result
        self._editor_view.render_btn.setEnabled(True)
        self._editor_view.stop_btn.setVisible(False)

        if result.is_cancelled:
            self._stop_render_preview()
            self._render_view.reset()
            self._switch_to_view(_VIEW_EDITOR)
            return

        self._render_view.set_global_progress(100, "Render complete!")
        self._render_view.set_platform_info(self.selected_platform, 100)
        self._render_view.show_done()
        self._render_view.preview.dimmed = False
        self._render_view.preview.update()

        if result.multipart:
            self._show_multipart_result(result)
            return

        outcome = result.first
        if outcome.is_failed:
            return

    def _on_render_queue_completed(self, event: RenderQueueCompleted) -> None:
        result = event.result
        self._editor_view.render_btn.setEnabled(bool(self.selected_targets))
        self._editor_view.stop_btn.setVisible(False)

        if result.is_cancelled:
            self._stop_render_preview()
            self._render_view.reset()
            self._switch_to_view(_VIEW_EDITOR)
            return

        self._render_view.set_global_progress(100, "Render complete!")
        for entry in result.entries:
            self._render_view.set_platform_info(self._target_label(entry.target), 100)
        self._render_view.show_done()
        self._render_view.preview.dimmed = False
        self._render_view.preview.update()

        self._show_queue_result(result)

    def _on_render_done(self) -> None:
        """Navigate back to editor after user clicks Done on render view."""
        self._stop_render_preview()
        self._render_view.reset()
        self._switch_to_view(_VIEW_EDITOR)

    def _start_render_preview(self) -> None:
        """Play the source video in a muted loop inside the render view preview."""
        if self._source_path is None:
            return

        self._render_view.preview.set_selection(
            self._editor_view.crop_widget.selection,
        )
        self._render_view.preview.split_ratio = self.split_ratio

        self._preview_trim_start_ms = int(
            self._editor_view.timeline.trim_start * 1000,
        )
        self._preview_trim_end_ms = int(
            self._editor_view.timeline.trim_end * 1000,
        )

        self._preview_audio = QAudioOutput()
        self._preview_audio.setVolume(0.0)

        self._preview_player = QMediaPlayer()
        self._preview_player.setAudioOutput(self._preview_audio)

        self._preview_sink = QVideoSink()
        self._preview_player.setVideoSink(self._preview_sink)
        self._preview_sink.videoFrameChanged.connect(self._on_preview_frame)
        self._preview_player.positionChanged.connect(self._on_preview_position)
        self._preview_player.mediaStatusChanged.connect(self._on_preview_status)

        self._render_view.preview.dimmed = True
        self._preview_player.setSource(
            QUrl.fromLocalFile(str(self._source_path)),
        )

    def _stop_render_preview(self) -> None:
        """Stop and clean up the render preview player."""
        if self._preview_player is not None:
            self._preview_player.stop()
            self._preview_player = None
        self._preview_audio = None
        self._preview_sink = None

    def _on_preview_frame(self, frame: QVideoFrame) -> None:
        img = frame.toImage()
        if img.isNull():
            return
        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
        self._render_view.preview.set_frame(img)

    def _on_preview_position(self, ms: int) -> None:
        if self._preview_player is None:
            return
        if ms < self._preview_trim_start_ms or ms >= self._preview_trim_end_ms:
            self._preview_player.setPosition(self._preview_trim_start_ms)

    def _on_preview_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._preview_player is None:
            return
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
        ):
            self._preview_player.setPosition(self._preview_trim_start_ms)
            self._preview_player.play()

    def _show_multipart_result(self, result: RenderJobResult) -> None:
        pass

    def _show_queue_result(self, result: RenderQueueResult) -> None:
        if not result.failures:
            return
        failed = ", ".join(
            self._target_label(entry.target) for entry in result.failures
        )
        QMessageBox.warning(
            self,
            "Render failed",
            f"Could not render: {failed}",
        )

    def _stop_render(self) -> None:
        self._bus.publish(StopRendering())

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        """Shut down the render worker and save config on exit."""
        if self._render_worker is not None and self._render_worker.isRunning():
            self._render_worker.stop()
            self._render_worker.wait()
        self._stop_render_preview()
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
            crops=self._editor_view.crop_widget.selection,
            selected_targets=tuple(
                TargetPreference(platform, format_key)
                for platform, format_key in self.selected_targets
            ),
        )
        SavePreferencesUseCase(self._prefs_repository).save(preferences)

    def _restore_crops(self) -> None:
        saved = self._prefs.crops
        current = self._editor_view.crop_widget.selection
        top = saved.top if not saved.top.is_empty else current.top
        bottom = saved.bottom if not saved.bottom.is_empty else current.bottom
        self._editor_view.crop_widget.set_selection(
            CropSelection(top=top, bottom=bottom),
        )

    # ---- keyboard ----

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
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
            self._editor_view.volume_control.toggle_mute()
        elif event.key() == Qt.Key_Question:  # ty: ignore[unresolved-attribute]
            self._show_keybindings_help()
        else:
            super().keyPressEvent(event)

    def _set_trim_start_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        updated = SetTrimStartUseCase().set_start(
            SetTrimStartRequest(self._editor_view.timeline.trim_range, pos),
        )
        self._editor_view.timeline.apply_range(updated)

    def _set_trim_end_to_playhead(self) -> None:
        if not self.video_info:
            return
        pos = self.player.position() / 1000.0
        updated = SetTrimEndUseCase().set_end(
            SetTrimEndRequest(
                self._editor_view.timeline.trim_range,
                pos,
                self.video_info.duration,
            ),
        )
        self._editor_view.timeline.apply_range(updated)

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
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Show the drop overlay when a file is dragged in."""
        if event.mimeData().hasUrls():
            self._drop_overlay.setGeometry(self._stack.rect())
            self._drop_overlay.show()
            self._drop_overlay.raise_()
            event.acceptProposedAction()

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Hide the drop overlay when the drag leaves."""
        self._drop_overlay.hide()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
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

    @staticmethod
    def _target_label(target: RenderTarget) -> str:
        return f"{target.platform.upper()} / {target.format_key.upper()}"


def run(file_path: str | None = None) -> None:
    """Launch the Trimmy application."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        logger.error(
            "ffmpeg and ffprobe must be installed and in PATH.",
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    load_fonts()

    default_font = QFont(Typography.BODY)
    default_font.setPixelSize(Typography.BODY_MD_SIZE)
    default_font.setWeight(QFont.Weight(Typography.BODY_WEIGHT))
    app.setFont(default_font)

    win = MainWindow(file_path)
    win.show()
    sys.exit(app.exec())
