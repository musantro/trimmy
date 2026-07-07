"""Main application window and render worker."""

from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from PySide6.QtCore import QSize, Qt, QThread, QUrl
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
    QAudioBuffer,
    QAudioBufferOutput,
    QAudioOutput,
    QMediaPlayer,
    QVideoFrame,
    QVideoSink,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from trimmy import __version__
from trimmy.app.components import (
    DropOverlay,
    KeybindingsDialog,
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
from trimmy.app.theme import (
    Colors,
    Radii,
    Spacing,
    Typography,
    build_stylesheet,
    load_fonts,
)
from trimmy.app.views.editor_view import EditorView
from trimmy.app.views.render_view import RenderView
from trimmy.app.views.startup_view import StartupView
from trimmy.app.widgets import PreviewWidget
from trimmy.editing.crop.domain.services import AspectRatioCalculator
from trimmy.editing.shared.domain.models import CropSelection
from trimmy.editing.trim.application.set_trim_end_use_case import (
    SetTrimEndRequest,
    SetTrimEndUseCase,
)
from trimmy.editing.trim.application.set_trim_start_at_playhead_use_case import (
    SetTrimStartAtPlayheadRequest,
    SetTrimStartAtPlayheadUseCase,
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


def _fmt_seconds(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}:{secs:04.1f}"


@dataclass(frozen=True)
class QueuedRenderJob:
    """A user-visible queued render snapshot."""

    item: RenderQueueItem
    source_name: str
    output_path: Path
    trim_start: float
    trim_end: float
    split_ratio: float


@dataclass(frozen=True)
class QueuedRenderGroup:
    """One queued trim with all selected platform targets."""

    jobs: tuple[QueuedRenderJob, ...]

    @property
    def first(self) -> QueuedRenderJob:
        """Return the first output job for preview metadata."""
        return self.jobs[0]


class RenderQueueDialog(QDialog):
    """Review queued trims and outputs before starting a batch render."""

    EDIT_RESULT = 2

    def __init__(
        self,
        groups: tuple[QueuedRenderGroup, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._groups = list(groups)
        self._edit_index: int | None = None
        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._sink: QVideoSink | None = None
        self._trim_start_ms = 0
        self._trim_end_ms = 0

        self.setWindowTitle("Review Render Queue")
        self.setMinimumSize(920, 620)
        self.setStyleSheet(
            f"QDialog {{ background: {Colors.LEVEL_1}; }}"
            f"QListWidget {{ background: {Colors.SURFACE_CONTAINER_LOW};"
            f" color: {Colors.ON_SURFACE}; border: 1px solid {Colors.OUTLINE_VARIANT};"
            f" border-radius: {Radii.DEFAULT}px; }}"
            f"QListWidget::item {{ padding: {Spacing.XS}px; }}"
            "QListWidget::item:selected {"
            f" background: {Colors.SURFACE_CONTAINER_HIGHEST};"
            " }"
            f"QLabel {{ color: {Colors.ON_SURFACE}; background: transparent; }}"
            f"QDialogButtonBox QPushButton {{ background: {Colors.PRIMARY_CONTAINER};"
            f" color: {Colors.ON_PRIMARY_CONTAINER}; border: none;"
            f" border-radius: {Radii.DEFAULT}px;"
            f" padding: {Spacing.XS}px {Spacing.SM}px;"
            f" font-family: '{Typography.MONO}'; }}"
            "QDialogButtonBox QPushButton:hover {"
            f" background: {Colors.PRIMARY_DIM};"
            " }",
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        root.setSpacing(Spacing.SM)

        total_targets = sum(len(group.jobs) for group in self._groups)
        self._title = QLabel(
            f"Render Queue ({len(self._groups)} jobs, {total_targets} outputs)",
        )
        title_font = QFont(Typography.HEADING)
        title_font.setPixelSize(Typography.BODY_LG_SIZE)
        title_font.setWeight(QFont.Weight(Typography.HEADLINE_WEIGHT))
        self._title.setFont(title_font)
        root.addWidget(self._title)

        body = QHBoxLayout()
        body.setSpacing(Spacing.MD)
        root.addLayout(body, stretch=1)

        self._list = QListWidget()
        self._list.setMinimumWidth(480)
        self._list.currentRowChanged.connect(self._select_job)
        body.addWidget(self._list, stretch=1)

        preview_panel = QVBoxLayout()
        preview_panel.setSpacing(Spacing.SM)
        body.addLayout(preview_panel)

        self._preview = PreviewWidget()
        self._preview.setFixedSize(180, 320)
        self._preview.interactive = False
        preview_panel.addWidget(self._preview, alignment=Qt.AlignHCenter)  # ty: ignore[unresolved-attribute]

        self._output_label = QLabel()
        self._output_label.setWordWrap(True)
        self._output_label.setObjectName("info")
        self._output_label.setMaximumWidth(260)
        preview_panel.addWidget(self._output_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
        )
        self._render_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._render_btn.setText("Render Queue")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_list(selected_row=0)

    @property
    def groups(self) -> tuple[QueuedRenderGroup, ...]:
        """Return queued groups after any dialog edits."""
        return tuple(self._groups)

    @property
    def edit_index(self) -> int | None:
        """Return selected group index when the dialog requests editing."""
        return self._edit_index

    def _refresh_list(self, *, selected_row: int) -> None:
        total_targets = sum(len(group.jobs) for group in self._groups)
        self._title.setText(
            f"Render Queue ({len(self._groups)} jobs, {total_targets} outputs)",
        )
        self._list.blockSignals(True)  # noqa: FBT003
        self._list.clear()
        for index, group in enumerate(self._groups, start=1):
            self._list.addItem(self._queue_item(index, group))
        self._list.blockSignals(False)  # noqa: FBT003

        has_groups = bool(self._groups)
        self._render_btn.setEnabled(has_groups)
        if not has_groups:
            self._output_label.setText("No jobs queued")
            self._preview.frame = None
            self._preview.update()
            return

        selected_row = max(0, min(selected_row, len(self._groups) - 1))
        self._list.setCurrentRow(selected_row)

    def _queue_item(self, index: int, group: QueuedRenderGroup) -> QListWidgetItem:
        item = QListWidgetItem(self._queue_item_text(index, group))
        item.setSizeHint(QSize(0, 104))
        return item

    def _queue_item_text(self, index: int, group: QueuedRenderGroup) -> str:
        first = group.first
        targets_text = ", ".join(
            f"{job.item.target.platform.upper()} / {job.item.target.format_key.upper()}"
            for job in group.jobs
        )
        trim_text = (
            f"Trim {_fmt_seconds(first.trim_start)} - {_fmt_seconds(first.trim_end)}"
        )
        return "\n".join((f"{index}. {first.source_name}", trim_text, targets_text))

    def _select_job(self, row: int) -> None:
        if row < 0 or row >= len(self._groups):
            return
        self._install_selected_row_widget(row)
        group = self._groups[row]
        job = group.first
        spec = job.item.spec
        self._preview.set_selection(spec.crops)
        self._preview.split_ratio = job.split_ratio
        self._output_label.setText(f"{len(group.jobs)} outputs selected")
        self._trim_start_ms = int(job.trim_start * 1000)
        self._trim_end_ms = int(job.trim_end * 1000)

        self._stop_preview()
        self._audio = QAudioOutput()
        self._audio.setVolume(0.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio)
        self._sink = QVideoSink()
        self._player.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._on_preview_frame)
        self._player.positionChanged.connect(self._on_preview_position)
        self._player.mediaStatusChanged.connect(self._on_preview_status)
        self._player.setSource(QUrl.fromLocalFile(str(spec.source_path)))

    def _install_selected_row_widget(self, row: int) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            self._list.removeItemWidget(item)
            if index < len(self._groups):
                item.setText(self._queue_item_text(index + 1, self._groups[index]))

        item = self._list.item(row)
        item.setText("")
        self._list.setItemWidget(item, self._selected_row_widget(row))

    def _selected_row_widget(self, row: int) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(Spacing.XS, Spacing.XS, Spacing.XS, Spacing.XS)
        layout.setSpacing(Spacing.XS)

        text = QLabel(self._queue_item_text(row + 1, self._groups[row]))
        text.setWordWrap(True)
        text.setStyleSheet("background: transparent;")
        layout.addWidget(text, stretch=1)

        modify_btn = QPushButton("Modify")
        modify_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        modify_btn.setStyleSheet(self._inline_button_style())
        modify_btn.clicked.connect(lambda: self._modify_selected(row))
        layout.addWidget(modify_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setCursor(Qt.PointingHandCursor)  # ty: ignore[unresolved-attribute]
        delete_btn.setStyleSheet(self._inline_delete_button_style())
        delete_btn.clicked.connect(lambda: self._delete_selected(row))
        layout.addWidget(delete_btn)

        return wrapper

    def _delete_selected(self, row: int | None = None) -> None:
        if row is None:
            row = self._list.currentRow()
        if row < 0 or row >= len(self._groups):
            return
        del self._groups[row]
        self._refresh_list(selected_row=row)

    def _modify_selected(self, row: int | None = None) -> None:
        if row is None:
            row = self._list.currentRow()
        if row < 0 or row >= len(self._groups):
            return
        self._edit_index = row
        self.done(self.EDIT_RESULT)

    @staticmethod
    def _inline_button_style() -> str:
        return (
            f"QPushButton {{ background: {Colors.PRIMARY_CONTAINER};"
            f" color: {Colors.ON_PRIMARY_CONTAINER}; border: none;"
            f" border-radius: {Radii.DEFAULT}px;"
            f" padding: {Spacing.XS}px {Spacing.SM}px;"
            f" font-family: '{Typography.MONO}'; }}"
            f"QPushButton:hover {{ background: {Colors.PRIMARY_DIM}; }}"
        )

    @staticmethod
    def _inline_delete_button_style() -> str:
        return (
            f"QPushButton {{ background: transparent; color: {Colors.ERROR};"
            f" border: 1px solid {Colors.ERROR};"
            f" border-radius: {Radii.DEFAULT}px;"
            f" padding: {Spacing.XS}px {Spacing.SM}px;"
            f" font-family: '{Typography.MONO}'; }}"
            f"QPushButton:hover {{ background: {Colors.ERROR_CONTAINER}; }}"
        )

    def _on_preview_frame(self, frame: QVideoFrame) -> None:
        img = frame.toImage()
        if img.isNull():
            return
        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
        self._preview.set_frame(img)

    def _on_preview_position(self, ms: int) -> None:
        if self._player is None:
            return
        if ms < self._trim_start_ms or ms >= self._trim_end_ms:
            self._player.setPosition(self._trim_start_ms)

    def _on_preview_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._player is None:
            return
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.EndOfMedia,
        ):
            self._player.setPosition(self._trim_start_ms)
            self._player.play()

    def _stop_preview(self) -> None:
        if self._player is not None:
            self._player.stop()
        self._player = None
        self._audio = None
        self._sink = None

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_preview()
        super().closeEvent(event)

    @override
    def done(self, result: int) -> None:
        self._stop_preview()
        super().done(result)


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
        self._last_video_folder = self._prefs.last_video_folder
        self._last_output_folder = self._prefs.last_output_folder
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
        self._render_queue: list[QueuedRenderGroup] = []
        self._active_render_groups: tuple[QueuedRenderGroup, ...] = ()
        self._active_item_group_indexes: tuple[int, ...] = ()
        self._active_item_progress: dict[int, int] = {}
        self._active_preview_group_index: int | None = None
        self._rendering_saved_queue = False
        self._preview_player: QMediaPlayer | None = None
        self._preview_audio: QAudioOutput | None = None
        self._preview_sink: QVideoSink | None = None

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self._volume = self._prefs.volume
        self.audio.setVolume(self._volume / 100.0)
        self.player.setAudioOutput(self.audio)
        self.audio_buffer = QAudioBufferOutput()
        self.player.setAudioBufferOutput(self.audio_buffer)
        self.audio_buffer.audioBufferReceived.connect(self._on_audio_buffer)
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
        self._sync_queue_controls()

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

        # Body: stacked views
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

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
        self._editor_view.flip_split_btn.clicked.connect(self._flip_split)
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
        self._editor_view.send_queue_btn.clicked.connect(self._send_to_queue)
        self._editor_view.render_queue_btn.clicked.connect(self._render_job_queue)
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
        self._sync_queue_controls()

        # Index 2: Render view
        self._render_view = RenderView()
        self._render_view.cancel_requested.connect(self._stop_render)
        self._render_view.done_requested.connect(self._on_render_done)
        self._render_view.queue_job_selected.connect(self._on_render_queue_job_selected)
        self._stack.addWidget(self._render_view)

        self._stack.setCurrentIndex(_VIEW_STARTUP)
        body.addWidget(self._stack)

        root.addLayout(body)

        # Drop overlay parented to the stacked widget
        self._drop_overlay = DropOverlay(self._stack)
        self._drop_overlay.hide()

    def _switch_to_view(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ---- file open ----

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            self._dialog_start_folder(self._last_video_folder),
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
        self._last_video_folder = str(path.parent)

        self._editor_view.crop_widget.set_source_size(info.width, info.height)
        self._editor_view.crop_widget.init_crops()
        self._restore_crops()
        self._editor_view.timeline.set_duration(info.duration)
        self._editor_view.audio_meter.configure(
            channels=info.audio_channels,
            sample_rate=info.audio_sample_rate,
            codec=info.audio_codec,
        )
        self._update_crop_aspects()

        self._waiting_first_frame = True
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

        self.setWindowTitle(f"Trimmy — {path.name}")

        self._switch_to_view(_VIEW_EDITOR)

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
            self._editor_view.audio_meter.reset_levels()

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
            self._editor_view.audio_meter.reset_levels()

    def _on_audio_buffer(self, buffer: QAudioBuffer) -> None:
        self._editor_view.audio_meter.set_buffer(buffer)

    # ---- playback ----

    def _toggle_play(self) -> None:
        if not self.video_info:
            self._open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._editor_view.playback.set_playing(playing=False)
            self._editor_view.audio_meter.reset_levels()
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

    def _flip_split(self) -> None:
        self.split_ratio = self._editor_view.crop_widget.flip_output_areas(
            self.split_ratio,
        )
        self._editor_view.preview.split_ratio = self.split_ratio
        self._editor_view.preview.update()
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
        self._editor_view.send_queue_btn.setEnabled(bool(self.selected_targets))

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

        output_paths = self._choose_output_paths(src, targets)
        if output_paths is None:
            return

        self._editor_view.render_btn.setEnabled(False)
        self._editor_view.send_queue_btn.setEnabled(False)
        self._editor_view.render_queue_btn.setEnabled(False)
        self._editor_view.stop_btn.setVisible(True)
        self._rendering_saved_queue = False
        self._active_render_groups = ()
        self._active_item_group_indexes = ()
        self._active_item_progress = {}
        self._active_preview_group_index = None

        jobs = self._build_render_jobs(src, targets, output_paths)
        items = [job.item for job in jobs]
        for job in jobs:
            self._render_view.set_platform_info(self._target_label(job.item.target), 0)

        self._render_out_path = str(next(iter(output_paths.values())))
        self._bus.publish(StartRenderQueue(tuple(items)))

        self._switch_to_view(_VIEW_RENDER)
        self._start_render_preview()

    def _send_to_queue(self) -> None:
        if not self.video_info or self._source_path is None:
            return
        src = self._source_path
        targets = self._editor_view.platform_selector.selected_targets()
        if not targets:
            return

        group_number = len(self._render_queue) + 1
        output_paths = self._choose_output_paths(
            src,
            targets,
            queue_suffix=group_number,
        )
        if output_paths is None:
            return

        self._render_queue.append(
            QueuedRenderGroup(
                self._build_render_jobs(src, targets, output_paths),
            ),
        )
        self._sync_queue_controls()

    def _render_job_queue(self) -> None:
        if not self._render_queue:
            return

        dialog = RenderQueueDialog(tuple(self._render_queue), self)
        result = dialog.exec()
        self._render_queue = list(dialog.groups)
        self._sync_queue_controls()

        if result == RenderQueueDialog.EDIT_RESULT:
            edit_index = dialog.edit_index
            if edit_index is not None:
                self._edit_queued_group(edit_index)
            return

        if result != QDialog.DialogCode.Accepted or not self._render_queue:
            return

        self._editor_view.render_btn.setEnabled(False)
        self._editor_view.send_queue_btn.setEnabled(False)
        self._editor_view.render_queue_btn.setEnabled(False)
        self._editor_view.stop_btn.setVisible(True)
        self._render_view.reset()
        self._rendering_saved_queue = True

        queued_jobs = tuple(job for group in self._render_queue for job in group.jobs)
        items = tuple(job.item for job in queued_jobs)
        self._active_render_groups = tuple(self._render_queue)
        self._active_item_group_indexes = tuple(
            group_index
            for group_index, group in enumerate(self._active_render_groups)
            for _job in group.jobs
        )
        self._active_item_progress = dict.fromkeys(range(len(queued_jobs)), 0)
        self._active_preview_group_index = 0
        self._render_view.set_queue_jobs(
            tuple(
                self._queue_group_label(index, group)
                for index, group in enumerate(self._active_render_groups)
            ),
        )
        self._render_out_path = str(queued_jobs[0].output_path)
        self._bus.publish(StartRenderQueue(items))

        self._switch_to_view(_VIEW_RENDER)
        self._show_render_queue_group(0, force=True)

    def _choose_output_paths(
        self,
        src: Path,
        targets: tuple[tuple[str, str], ...],
        *,
        queue_suffix: int | None = None,
    ) -> dict[tuple[str, str], Path] | None:
        reserved = self._queued_output_paths()
        if len(targets) == 1:
            platform, format_key = targets[0]
            default_name = self._default_output_name(
                src, platform, format_key, queue_suffix
            )
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Rendered Video",
                str(self._output_dialog_folder(src) / default_name),
                "MP4 Files (*.mp4)",
            )
            if not out_path:
                return None
            selected = Path(out_path)
            self._last_output_folder = str(selected.parent)
            return {targets[0]: self._available_output_path(selected, reserved)}

        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose Render Output Folder",
            str(self._output_dialog_folder(src)),
        )
        if not out_dir:
            return None
        output_root = Path(out_dir)
        self._last_output_folder = str(output_root)
        paths: dict[tuple[str, str], Path] = {}
        for platform, format_key in targets:
            path = output_root / self._default_output_name(
                src,
                platform,
                format_key,
                queue_suffix,
            )
            paths[(platform, format_key)] = self._available_output_path(path, reserved)
            reserved.add(paths[(platform, format_key)])
        return paths

    def _build_render_jobs(
        self,
        src: Path,
        targets: tuple[tuple[str, str], ...],
        output_paths: dict[tuple[str, str], Path],
    ) -> tuple[QueuedRenderJob, ...]:
        if self.video_info is None:
            return ()

        jobs: list[QueuedRenderJob] = []
        trim_range = self._editor_view.timeline.trim_range
        crops = self._editor_view.crop_widget.selection
        for platform, format_key in targets:
            fmt = self._get_format(platform, format_key)
            target = RenderTarget(platform, format_key, self.selected_quality)
            spec = RenderSpec(
                source_path=src,
                output_path=output_paths[(platform, format_key)],
                trim=trim_range,
                crops=crops,
                split_ratio=self.split_ratio,
                platform=platform,
                quality=self.selected_quality,
                source_fps=self.video_info.fps,
            )
            jobs.append(
                QueuedRenderJob(
                    item=RenderQueueItem(target, spec, fmt.max_duration),
                    source_name=src.name,
                    output_path=output_paths[(platform, format_key)],
                    trim_start=trim_range.start,
                    trim_end=trim_range.end,
                    split_ratio=self.split_ratio,
                ),
            )
        return tuple(jobs)

    def _edit_queued_group(self, group_index: int) -> None:
        if group_index < 0 or group_index >= len(self._render_queue):
            return
        group = self._render_queue[group_index]
        job = group.first
        spec = job.item.spec
        if not spec.source_path.exists():
            QMessageBox.warning(
                self,
                "Video missing",
                f"Could not reopen queued video:\n{spec.source_path}",
            )
            return

        self._render_queue.pop(group_index)
        self.open_file(spec.source_path)
        if self._source_path != spec.source_path or self.video_info is None:
            self._render_queue.insert(group_index, group)
            self._sync_queue_controls()
            return

        targets = tuple(
            (item.item.target.platform, item.item.target.format_key)
            for item in group.jobs
        )
        first_target = group.first.item.target
        self.selected_platform = first_target.platform
        self.selected_format = first_target.format_key
        self.selected_quality = first_target.quality
        self.selected_targets = targets
        self.split_ratio = job.split_ratio

        self._editor_view.platform_selector.blockSignals(True)  # noqa: FBT003
        self._editor_view.platform_selector.set_platform(self.selected_platform)
        self._editor_view.platform_selector.set_format(
            self.selected_platform,
            self.selected_format,
        )
        self._editor_view.platform_selector.set_targets(targets)
        self._editor_view.platform_selector.blockSignals(False)  # noqa: FBT003

        self._editor_view.preview.split_ratio = self.split_ratio
        self._editor_view.timeline.apply_range(spec.trim)
        self._editor_view.crop_widget.set_selection(spec.crops)
        self._on_crops_changed()
        self.player.setPosition(int(spec.trim.start * 1000))
        self._switch_to_view(_VIEW_EDITOR)
        self._sync_queue_controls()

    def _default_output_name(
        self,
        src: Path,
        platform: str,
        format_key: str,
        queue_suffix: int | None,
    ) -> str:
        suffix = f"_{queue_suffix}" if queue_suffix is not None else ""
        return f"{src.stem}{suffix}_{platform}_{format_key}_{self.selected_quality}.mp4"

    def _queued_output_paths(self) -> set[Path]:
        return {job.output_path for group in self._render_queue for job in group.jobs}

    @staticmethod
    def _available_output_path(path: Path, reserved: set[Path]) -> Path:
        if path not in reserved and not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        for index in range(1, 10_000):
            candidate = path.with_name(f"{stem}_{index}{suffix}")
            if candidate not in reserved and not candidate.exists():
                return candidate
        return path

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
        label = self._target_label(event.target)
        if self._rendering_saved_queue and event.item_index < len(
            self._active_item_group_indexes,
        ):
            self._active_item_progress[event.item_index] = event.target_pct
            group_index = self._active_item_group_indexes[event.item_index]
            self._render_view.set_queue_job_progress(
                group_index,
                self._queue_group_progress(group_index),
                self._target_label(event.target),
            )
            if self._active_preview_group_index == group_index:
                self._refresh_render_queue_group_details(group_index)
            return
        self._render_view.set_platform_info(label, event.target_pct)

    def _on_render_completed(self, event: RenderCompleted) -> None:
        result = event.result
        self._editor_view.render_btn.setEnabled(bool(self.selected_targets))
        self._editor_view.stop_btn.setVisible(False)
        self._sync_queue_controls()

        if result.is_cancelled:
            self._stop_render_preview()
            self._render_view.reset()
            self._active_render_groups = ()
            self._active_item_group_indexes = ()
            self._active_item_progress = {}
            self._active_preview_group_index = None
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
        self._sync_queue_controls()

        if result.is_cancelled:
            self._stop_render_preview()
            self._render_view.reset()
            self._active_render_groups = ()
            self._active_item_group_indexes = ()
            self._active_item_progress = {}
            self._active_preview_group_index = None
            self._switch_to_view(_VIEW_EDITOR)
            return

        self._render_view.set_global_progress(100, "Render complete!")
        for item_index, entry in enumerate(result.entries):
            if self._rendering_saved_queue:
                self._active_item_progress[item_index] = 100
            else:
                self._render_view.set_platform_info(
                    self._target_label(entry.target), 100
                )
        if self._rendering_saved_queue:
            for group_index in range(len(self._active_render_groups)):
                self._render_view.set_queue_job_progress(group_index, 100, "")
            if self._active_preview_group_index is not None:
                self._refresh_render_queue_group_details(
                    self._active_preview_group_index,
                )
        self._render_view.show_done()
        self._render_view.preview.dimmed = False
        self._render_view.preview.update()

        self._show_queue_result(result)
        if self._rendering_saved_queue and not result.failures:
            self._render_queue.clear()
            self._active_render_groups = ()
            self._active_item_group_indexes = ()
            self._active_item_progress = {}
            self._active_preview_group_index = None
            self._rendering_saved_queue = False
            self._sync_queue_controls()

    def _on_render_done(self) -> None:
        """Navigate back to editor after user clicks Done on render view."""
        self._stop_render_preview()
        self._render_view.reset()
        self._switch_to_view(_VIEW_EDITOR)

    def _start_render_preview(self) -> None:
        """Play the source video in a muted loop inside the render view preview."""
        if self._source_path is None:
            return
        self._stop_render_preview()

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

    def _start_render_preview_for_job(self, job: QueuedRenderJob) -> None:
        """Play a queued job source in a muted loop inside the render preview."""
        self._stop_render_preview()
        spec = job.item.spec
        self._render_view.preview.set_selection(spec.crops)
        self._render_view.preview.split_ratio = job.split_ratio

        self._preview_trim_start_ms = int(job.trim_start * 1000)
        self._preview_trim_end_ms = int(job.trim_end * 1000)

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
            QUrl.fromLocalFile(str(spec.source_path)),
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

    def _on_render_queue_job_selected(self, group_index: int) -> None:
        self._show_render_queue_group(group_index, force=True)

    def _show_render_queue_group(
        self, group_index: int, *, force: bool = False
    ) -> None:
        if group_index < 0 or group_index >= len(self._active_render_groups):
            return
        if force or self._active_preview_group_index != group_index:
            self._active_preview_group_index = group_index
            self._start_render_preview_for_job(
                self._active_render_groups[group_index].first
            )
        self._refresh_render_queue_group_details(group_index)

    def _refresh_render_queue_group_details(self, group_index: int) -> None:
        rows: list[tuple[str, int]] = []
        for item_index, owner in enumerate(self._active_item_group_indexes):
            if owner != group_index:
                continue
            target = (
                self._active_render_groups[group_index]
                .jobs[self._group_local_item_index(group_index, item_index)]
                .item.target
            )
            rows.append(
                (
                    self._target_label(target),
                    self._active_item_progress.get(item_index, 0),
                ),
            )
        self._render_view.set_platform_progress_items(tuple(rows))

    def _group_local_item_index(self, group_index: int, item_index: int) -> int:
        return sum(
            1
            for index, owner in enumerate(self._active_item_group_indexes[:item_index])
            if owner == group_index
        )

    def _queue_group_progress(self, group_index: int) -> int:
        if group_index < 0 or group_index >= len(self._active_render_groups):
            return 0
        item_indexes = [
            index
            for index, owner in enumerate(self._active_item_group_indexes)
            if owner == group_index
        ]
        if not item_indexes:
            return 0
        total = sum(self._active_item_progress.get(index, 0) for index in item_indexes)
        return int(total / len(item_indexes))

    def _queue_group_label(self, index: int, group: QueuedRenderGroup) -> str:
        first = group.first
        return (
            f"Job {index + 1}: {first.source_name} "
            f"({_fmt_seconds(first.trim_start)}-{_fmt_seconds(first.trim_end)})"
        )

    @staticmethod
    def _queue_target_label(item_index: int, target: RenderTarget) -> str:
        return f"{item_index + 1}. {MainWindow._target_label(target)}"

    def _sync_queue_controls(self) -> None:
        count = len(self._render_queue)
        running = self._render_worker is not None and self._render_worker.isRunning()
        has_targets = bool(self.selected_targets)
        self._editor_view.send_queue_btn.setEnabled(has_targets and not running)
        self._editor_view.render_queue_btn.setEnabled(count > 0 and not running)
        self._editor_view.queue_status.setText(
            "QUEUE EMPTY"
            if count == 0
            else f"{count} JOB{'S' if count != 1 else ''} QUEUED",
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
            last_video_folder=self._last_video_folder,
            last_output_folder=self._last_output_folder,
            selected_targets=tuple(
                TargetPreference(platform, format_key)
                for platform, format_key in self.selected_targets
            ),
        )
        SavePreferencesUseCase(self._prefs_repository).save(preferences)

    @staticmethod
    def _dialog_start_folder(folder: str) -> str:
        path = Path(folder)
        return str(path) if folder and path.is_dir() else ""

    def _output_dialog_folder(self, src: Path) -> Path:
        folder = Path(self._last_output_folder)
        return folder if self._last_output_folder and folder.is_dir() else src.parent

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
        updated = SetTrimStartAtPlayheadUseCase().set_start(
            SetTrimStartAtPlayheadRequest(
                self._editor_view.timeline.trim_range,
                pos,
                self.video_info.duration,
            ),
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
    from trimmy.app.control_server import ControlServer  # noqa: PLC0415

    win._control_server = ControlServer(win)  # ty: ignore[unresolved-attribute]
    win.show()
    sys.exit(app.exec())
