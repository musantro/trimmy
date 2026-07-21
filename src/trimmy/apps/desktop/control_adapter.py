"""Adapter from the generic control port to the PySide main window."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from trimmy.apps.cli.domain.models import ControlError, JsonMap, Payload
from trimmy.apps.desktop.main_window import QueuedRenderGroup, QueuedRenderJob
from trimmy.editing.crop.domain.models import CropPosition, CropRect
from trimmy.rendering.domain.messages import StartRenderQueue, StopRendering


class MainWindowControlAdapter:
    """Expose a :class:`MainWindow` through the control-layer port."""

    def __init__(self, window: Any) -> None:
        self._window = window

    def ping(self) -> Payload:
        return Payload(data={"message": "Trimmy is running"})

    def state(self) -> Payload:
        window = self._window
        timeline = window._editor_view.timeline
        selection = window._editor_view.crop_widget.selection
        return Payload(
            data={
                "view": self._view_name(window._stack.currentIndex()),
                "source_path": str(window._source_path)
                if window._source_path
                else None,
                "video": self._video_state(),
                "playback": {
                    "state": self._playback_state(),
                    "position": window.player.position() / 1000.0,
                    "volume": window._volume,
                    "muted": window._editor_view.volume_control.is_muted(),
                },
                "trim": {
                    "start": timeline.trim_start,
                    "end": timeline.trim_end,
                    "duration": timeline.trim_end - timeline.trim_start,
                },
                "crops": {
                    "top": self._crop_rect(selection.top),
                    "bottom": self._crop_rect(selection.bottom),
                },
                "split_ratio": window.split_ratio,
                "selected_platform": window.selected_platform,
                "selected_quality": window.selected_quality,
                "targets": [
                    {"platform": platform, "format": format_key}
                    for platform, format_key in window.selected_targets
                ],
                "queue": self._queue_state(),
                "render": self.render_status().to_json(),
                "dialog": self.dialog_state().to_json(),
            }
        )

    def screenshot(self, output: Path | None, target: str) -> Payload:
        widget = self._screenshot_widget(target)
        output = output or self._default_screenshot_path()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not widget.grab().save(str(output)):
            raise ControlError(
                "screenshot_failed",
                f"Could not save screenshot to {output}",
            )
        return Payload(
            data={"message": f"Saved screenshot to {output}", "path": str(output)}
        )

    def close(self) -> Payload:
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
        return Payload(data={"message": "Trimmy is closing"})

    def dialog_state(self) -> Payload:
        modal = QApplication.activeModalWidget()
        if modal is None:
            return Payload(data={"open": False, "title": None})
        return Payload(data={"open": True, "title": modal.windowTitle()})

    def dialog_close(self) -> Payload:
        modal = QApplication.activeModalWidget()
        if modal is not None:
            modal.close()
        return Payload(
            data={"message": "Dialog closed" if modal is not None else "No dialog open"}
        )

    def dialog_help_open(self) -> Payload:
        QTimer.singleShot(0, self._window._show_keybindings_help)
        return Payload(data={"message": "Help dialog opened"})

    def file_open(self, path: Path) -> Payload:
        if not path.exists():
            raise ControlError("file_not_found", f"File not found: {path}")
        before = self._window._source_path
        self._window.open_file(path)
        if self._window._source_path == before and before != path:
            raise ControlError("video_probe_failed", f"Could not read video: {path}")
        return Payload(data={"message": f"Opened {path}", "path": str(path)})

    def playback_set(self, state: str) -> Payload:
        self._require_video()
        player = self._window.player
        playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if (state == "playing" and not playing) or (state == "paused" and playing):
            self._window._toggle_play()
        return Payload(data={"message": f"Playback {state}"})

    def playback_seek(self, seconds: float) -> Payload:
        self._require_video()
        self._window._on_seek(max(0.0, seconds))
        return Payload(data={"message": f"Seeked to {seconds:.3f}s"})

    def playback_volume(self, value: int) -> Payload:
        self._window._editor_view.volume_control.set_volume(value)
        self._window._on_volume_changed(value)
        return Payload(data={"message": f"Volume set to {value}"})

    def playback_mute(self, state: str) -> Payload:
        control = self._window._editor_view.volume_control
        should_mute = state == "muted"
        if control.is_muted() != should_mute:
            control.toggle_mute()
        return Payload(data={"message": f"Audio {state}"})

    def trim_set(self, start: float | str | None, end: float | str | None) -> Payload:
        self._require_video()
        timeline = self._window._editor_view.timeline
        start_value = (
            timeline.trim_start if start is None else self._resolve_time(start)
        )
        end_value = timeline.trim_end if end is None else self._resolve_time(end)
        if start_value >= end_value:
            raise ControlError("invalid_argument", "Trim start must be before trim end")
        updated = timeline.trim_range.with_start(start_value).with_end(
            end_value,
            timeline.duration,
        )
        timeline.apply_range(updated)
        return Payload(
            data={"message": f"Trim set to {updated.start:.3f}s-{updated.end:.3f}s"}
        )

    def crop_set(
        self,
        position: str,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> Payload:
        self._require_video()
        if w <= 0 or h <= 0:
            raise ControlError("invalid_crop", "Crop width and height must be positive")
        info = self._window.video_info
        if x < 0 or y < 0 or x + w > info.width or y + h > info.height:
            raise ControlError("invalid_crop", "Crop must fit inside the source frame")
        crop_position = CropPosition.TOP if position == "top" else CropPosition.BOTTOM
        selection = self._window._editor_view.crop_widget.selection.replace(
            crop_position,
            CropRect(x, y, w, h),
        )
        self._window._editor_view.crop_widget.set_selection(selection)
        self._window._on_crops_changed()
        return Payload(data={"message": f"{position} crop set"})

    def split_set(self, ratio: float) -> Payload:
        self._require_video()
        if ratio <= 0 or ratio >= 1:
            raise ControlError(
                "invalid_argument", "Split ratio must be between 0 and 1"
            )
        self._window._editor_view.preview.split_ratio = ratio
        self._window._on_split_changed(ratio)
        return Payload(data={"message": f"Split ratio set to {ratio:.3f}"})

    def split_flip(self) -> Payload:
        self._require_video()
        self._window._flip_split()
        return Payload(data={"message": "Split flipped"})

    def targets_set(self, targets: tuple[str, ...]) -> Payload:
        parsed = tuple(self._parse_target(target) for target in targets)
        self._window._editor_view.platform_selector.set_targets(parsed)
        self._window._on_target_selection_changed()
        return Payload(data={"message": f"Selected {len(parsed)} target(s)"})

    def targets_list(self) -> Payload:
        repo = self._window._presets
        platforms = ("instagram", "tiktok", "twitter", "whatsapp", "telegram")
        return Payload(
            data={
                "targets": [
                    {"platform": platform, "format": item.key, "label": item.label}
                    for platform in platforms
                    for item in repo.formats(platform)
                ],
            }
        )

    def quality_set(self, value: str) -> Payload:
        self._window.selected_quality = value
        self._window._update_crop_aspects()
        return Payload(data={"message": f"Quality set to {value}"})

    def queue_add(self, output: Path | None, output_dir: Path | None) -> Payload:
        self._require_video()
        jobs = self._jobs_for_outputs(
            output, output_dir, queue_suffix=len(self._window._render_queue) + 1
        )
        existing = self._find_queue_group(jobs)
        if existing is not None:
            return Payload(
                data={
                    "message": f"Queue entry already exists at index {existing}",
                    "index": existing,
                }
            )
        self._window._render_queue.append(QueuedRenderGroup(jobs))
        self._window._sync_queue_controls()
        return Payload(
            data={
                "message": f"Queued job {len(self._window._render_queue) - 1}",
                "index": len(self._window._render_queue) - 1,
            }
        )

    def queue_list(self) -> Payload:
        return Payload(data={"queue": self._queue_state()})

    def queue_remove(self, index: int) -> Payload:
        if index < 0 or index >= len(self._window._render_queue):
            raise ControlError(
                "queue_index_out_of_range", f"No queue item at index {index}"
            )
        del self._window._render_queue[index]
        self._window._sync_queue_controls()
        return Payload(data={"message": f"Removed queue item {index}"})

    def queue_edit(self, index: int) -> Payload:
        if index < 0 or index >= len(self._window._render_queue):
            raise ControlError(
                "queue_index_out_of_range", f"No queue item at index {index}"
            )
        self._window._edit_queued_group(index)
        return Payload(data={"message": f"Editing queue item {index}"})

    def queue_render(self) -> Payload:
        if not self._window._render_queue:
            raise ControlError("queue_index_out_of_range", "The render queue is empty")
        self._start_queue(tuple(self._window._render_queue), saved_queue=True)
        return Payload(data={"message": "Rendering queue"})

    def render_start(self, output: Path | None, output_dir: Path | None) -> Payload:
        self._require_video()
        if self._is_rendering():
            raise ControlError("render_in_progress", "A render is already running")
        jobs = self._jobs_for_outputs(output, output_dir, queue_suffix=None)
        self._start_queue((QueuedRenderGroup(jobs),), saved_queue=False)
        return Payload(data={"message": "Rendering started"})

    def render_stop(self) -> Payload:
        self._window._bus.publish(StopRendering())
        return Payload(data={"message": "Render stop requested"})

    def render_status(self) -> Payload:
        return Payload(
            data={
                "status": "running" if self._is_rendering() else "idle",
                "output_path": self._window._render_out_path,
                "saved_queue": self._window._rendering_saved_queue,
                "active_group_index": self._window._active_preview_group_index,
                "progress": dict(self._window._active_item_progress),
            }
        )

    def _require_video(self) -> None:
        if self._window.video_info is None or self._window._source_path is None:
            raise ControlError("no_video_loaded", "No video is loaded")

    def _resolve_time(self, value: float | str) -> float:
        if value == "playhead":
            return self._window.player.position() / 1000.0
        return float(value)

    def _parse_target(self, target: str) -> tuple[str, str]:
        if ":" not in target:
            raise ControlError("invalid_target", "Targets must use platform:format")
        platform, format_key = target.split(":", 1)
        valid = (
            {item.key for item in self._window._presets.formats(platform)}
            if self._known_platform(platform)
            else set()
        )
        if format_key not in valid:
            raise ControlError("invalid_target", f"Unknown target: {target}")
        return platform, format_key

    @staticmethod
    def _known_platform(platform: str) -> bool:
        return platform in {"instagram", "tiktok", "twitter", "whatsapp", "telegram"}

    def _jobs_for_outputs(
        self,
        output: Path | None,
        output_dir: Path | None,
        *,
        queue_suffix: int | None,
    ) -> tuple[QueuedRenderJob, ...]:
        targets = self._window._editor_view.platform_selector.selected_targets()
        if not targets:
            raise ControlError("invalid_target", "At least one target must be selected")
        if len(targets) == 1:
            if output is None:
                raise ControlError(
                    "output_required", "--output is required for one target"
                )
            output_paths = {targets[0]: output}
        else:
            if output_dir is None:
                raise ControlError(
                    "output_required", "--output-dir is required for multiple targets"
                )
            output_paths = {
                target: output_dir
                / self._window._default_output_name(
                    self._window._source_path,
                    target[0],
                    target[1],
                    queue_suffix,
                )
                for target in targets
            }
        return self._window._build_render_jobs(
            self._window._source_path,
            targets,
            output_paths,
        )

    def _find_queue_group(self, jobs: tuple[QueuedRenderJob, ...]) -> int | None:
        signature = self._job_signature(jobs)
        for index, group in enumerate(self._window._render_queue):
            if self._job_signature(group.jobs) == signature:
                return index
        return None

    @staticmethod
    def _job_signature(
        jobs: tuple[QueuedRenderJob, ...],
    ) -> tuple[tuple[str, str, str, float, float, float], ...]:
        return tuple(
            (
                str(job.item.spec.source_path),
                str(job.output_path),
                job.item.target.key,
                job.trim_start,
                job.trim_end,
                job.split_ratio,
            )
            for job in jobs
        )

    def _start_queue(
        self, groups: tuple[QueuedRenderGroup, ...], *, saved_queue: bool
    ) -> None:
        jobs = tuple(job for group in groups for job in group.jobs)
        self._window._editor_view.render_btn.setEnabled(False)
        self._window._editor_view.send_queue_btn.setEnabled(False)
        self._window._editor_view.render_queue_btn.setEnabled(False)
        self._window._editor_view.stop_btn.setVisible(True)
        self._window._render_view.reset()
        self._window._rendering_saved_queue = saved_queue
        self._window._active_render_groups = groups if saved_queue else ()
        self._window._active_item_group_indexes = tuple(
            group_index
            for group_index, group in enumerate(groups)
            for _job in group.jobs
        )
        self._window._active_item_progress = dict.fromkeys(range(len(jobs)), 0)
        self._window._active_preview_group_index = 0 if saved_queue else None
        if saved_queue:
            self._window._render_view.set_queue_jobs(
                tuple(
                    self._window._queue_group_label(index, group)
                    for index, group in enumerate(groups)
                ),
            )
        self._window._render_out_path = str(jobs[0].output_path)
        self._window._bus.publish(StartRenderQueue(tuple(job.item for job in jobs)))
        self._window._switch_to_view(2)
        if saved_queue:
            self._window._show_render_queue_group(0, force=True)
        else:
            self._window._start_render_preview()

    def _is_rendering(self) -> bool:
        worker = self._window._render_worker
        return bool(worker is not None and worker.isRunning())

    def _video_state(self) -> JsonMap | None:
        info = self._window.video_info
        if info is None:
            return None
        return {
            "duration": info.duration,
            "width": info.width,
            "height": info.height,
            "fps": info.fps,
            "audio_channels": info.audio_channels,
            "audio_sample_rate": info.audio_sample_rate,
            "audio_codec": info.audio_codec,
        }

    def _queue_state(self) -> list[JsonMap]:
        return [
            {
                "index": index,
                "source": group.first.source_name,
                "trim_start": group.first.trim_start,
                "trim_end": group.first.trim_end,
                "split_ratio": group.first.split_ratio,
                "jobs": [
                    {
                        "platform": job.item.target.platform,
                        "format": job.item.target.format_key,
                        "quality": job.item.target.quality,
                        "output_path": str(job.output_path),
                    }
                    for job in group.jobs
                ],
            }
            for index, group in enumerate(self._window._render_queue)
        ]

    def _screenshot_widget(self, target: str) -> Any:
        if target == "window":
            return self._window
        if target == "editor":
            return self._window._editor_view
        if target == "preview":
            return self._window._editor_view.preview
        if target == "render":
            return self._window._render_view
        raise ControlError("invalid_argument", f"Unknown screenshot target: {target}")

    @staticmethod
    def _default_screenshot_path() -> Path:
        return (
            Path(tempfile.gettempdir())
            / "trimmy"
            / f"screenshot-{uuid.uuid4().hex}.png"
        )

    def _playback_state(self) -> str:
        state = self._window.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            return "playing"
        if state == QMediaPlayer.PlaybackState.PausedState:
            return "paused"
        return "stopped"

    @staticmethod
    def _view_name(index: int) -> str:
        return {0: "startup", 1: "editor", 2: "render"}.get(index, "unknown")

    @staticmethod
    def _crop_rect(rect: CropRect) -> JsonMap:
        return {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h}
