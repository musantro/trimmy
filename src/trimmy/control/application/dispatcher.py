"""Dispatch parsed control requests to an application port."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from trimmy.control.domain.models import (
    AppPort,
    CommandArgs,
    ControlError,
    ControlRequest,
    CropArgs,
    NoArgs,
    OutputArgs,
    PathArgs,
    Payload,
    PlaybackStateArgs,
    QualityArgs,
    QueueIndexArgs,
    ScreenshotArgs,
    SecondsArgs,
    SplitArgs,
    TargetsArgs,
    TrimArgs,
    VolumeArgs,
)

CommandHandler = Callable[[CommandArgs, AppPort], Payload]
_ArgsT = TypeVar("_ArgsT", bound=CommandArgs)


def dispatch(request: ControlRequest, app: AppPort) -> Payload:
    """Dispatch *request* to *app* and return a result payload."""
    handler = COMMANDS.get(request.command)
    if handler is None:
        raise ControlError("invalid_command", f"Unknown command: {request.command}")
    return handler(request.args, app)


def _session_ping(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.ping()


def _session_state(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.state()


def _session_screenshot(args: CommandArgs, app: AppPort) -> Payload:
    screenshot = _expect(args, ScreenshotArgs)
    return app.screenshot(screenshot.output, screenshot.target)


def _session_close(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.close()


def _dialog_state(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.dialog_state()


def _dialog_close(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.dialog_close()


def _dialog_help(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.dialog_help_open()


def _file_open(args: CommandArgs, app: AppPort) -> Payload:
    path_args = _expect(args, PathArgs)
    return app.file_open(path_args.path)


def _playback_set(args: CommandArgs, app: AppPort) -> Payload:
    playback = _expect(args, PlaybackStateArgs)
    return app.playback_set(playback.state)


def _playback_seek(args: CommandArgs, app: AppPort) -> Payload:
    seconds = _expect(args, SecondsArgs)
    return app.playback_seek(seconds.seconds)


def _playback_volume(args: CommandArgs, app: AppPort) -> Payload:
    volume = _expect(args, VolumeArgs)
    return app.playback_volume(volume.value)


def _playback_mute(args: CommandArgs, app: AppPort) -> Payload:
    playback = _expect(args, PlaybackStateArgs)
    return app.playback_mute(playback.state)


def _trim_set(args: CommandArgs, app: AppPort) -> Payload:
    trim = _expect(args, TrimArgs)
    return app.trim_set(trim.start, trim.end)


def _crop_set(args: CommandArgs, app: AppPort) -> Payload:
    crop = _expect(args, CropArgs)
    return app.crop_set(crop.position, crop.x, crop.y, crop.w, crop.h)


def _split_set(args: CommandArgs, app: AppPort) -> Payload:
    split = _expect(args, SplitArgs)
    return app.split_set(split.ratio)


def _split_flip(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.split_flip()


def _targets_set(args: CommandArgs, app: AppPort) -> Payload:
    targets = _expect(args, TargetsArgs)
    return app.targets_set(targets.targets)


def _targets_list(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.targets_list()


def _quality_set(args: CommandArgs, app: AppPort) -> Payload:
    quality = _expect(args, QualityArgs)
    return app.quality_set(quality.value)


def _queue_add(args: CommandArgs, app: AppPort) -> Payload:
    output = _expect(args, OutputArgs)
    return app.queue_add(output.output, output.output_dir)


def _queue_list(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.queue_list()


def _queue_remove(args: CommandArgs, app: AppPort) -> Payload:
    index = _expect(args, QueueIndexArgs)
    return app.queue_remove(index.index)


def _queue_edit(args: CommandArgs, app: AppPort) -> Payload:
    index = _expect(args, QueueIndexArgs)
    return app.queue_edit(index.index)


def _queue_render(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.queue_render()


def _render_start(args: CommandArgs, app: AppPort) -> Payload:
    output = _expect(args, OutputArgs)
    return app.render_start(output.output, output.output_dir)


def _render_stop(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.render_stop()


def _render_status(args: CommandArgs, app: AppPort) -> Payload:
    _expect(args, NoArgs)
    return app.render_status()


COMMANDS: dict[str, CommandHandler] = {
    "session.ping": _session_ping,
    "session.state": _session_state,
    "session.screenshot": _session_screenshot,
    "session.close": _session_close,
    "dialog.state": _dialog_state,
    "dialog.close": _dialog_close,
    "dialog.help": _dialog_help,
    "file.open": _file_open,
    "playback.set": _playback_set,
    "playback.seek": _playback_seek,
    "playback.volume": _playback_volume,
    "playback.mute": _playback_mute,
    "trim.set": _trim_set,
    "crop.set": _crop_set,
    "split.set": _split_set,
    "split.flip": _split_flip,
    "targets.set": _targets_set,
    "targets.list": _targets_list,
    "quality.set": _quality_set,
    "queue.add": _queue_add,
    "queue.list": _queue_list,
    "queue.remove": _queue_remove,
    "queue.edit": _queue_edit,
    "queue.render": _queue_render,
    "render.start": _render_start,
    "render.stop": _render_stop,
    "render.status": _render_status,
}


def _expect(args: CommandArgs, expected: type[_ArgsT]) -> _ArgsT:
    if isinstance(args, expected):
        return args
    raise ControlError(
        "invalid_argument",
        f"{expected.__name__} required for command",
    )
