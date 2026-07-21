"""Argument parsing for Trimmy's single-entrypoint control CLI."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal, NoReturn, cast

from trimmy.apps.cli.domain.models import (
    AppProcessInstruction,
    CommandArgs,
    ControlError,
    ControlRequest,
    CropArgs,
    Instruction,
    JsonMap,
    LaunchInstruction,
    NoArgs,
    OutputArgs,
    PathArgs,
    PlaybackStateArgs,
    QualityArgs,
    QueueIndexArgs,
    ScreenshotArgs,
    SecondsArgs,
    SendInstruction,
    SplitArgs,
    TargetsArgs,
    TrimArgs,
    VolumeArgs,
)

_KNOWN = frozenset(
    {
        "ping",
        "state",
        "screenshot",
        "close",
        "dialog",
        "file",
        "playback",
        "trim",
        "crop",
        "split",
        "targets",
        "quality",
        "queue",
        "render",
    },
)

_REQUEST_ARG_TYPES: dict[str, type[CommandArgs]] = {
    "session.ping": NoArgs,
    "session.state": NoArgs,
    "session.screenshot": ScreenshotArgs,
    "session.close": NoArgs,
    "dialog.state": NoArgs,
    "dialog.close": NoArgs,
    "dialog.help": NoArgs,
    "file.open": PathArgs,
    "playback.set": PlaybackStateArgs,
    "playback.seek": SecondsArgs,
    "playback.volume": VolumeArgs,
    "playback.mute": PlaybackStateArgs,
    "trim.set": TrimArgs,
    "crop.set": CropArgs,
    "split.set": SplitArgs,
    "split.flip": NoArgs,
    "targets.set": TargetsArgs,
    "targets.list": NoArgs,
    "quality.set": QualityArgs,
    "queue.add": OutputArgs,
    "queue.list": NoArgs,
    "queue.remove": QueueIndexArgs,
    "queue.edit": QueueIndexArgs,
    "queue.render": NoArgs,
    "render.start": OutputArgs,
    "render.stop": NoArgs,
    "render.status": NoArgs,
}


def parse_request_payload(
    command: str, args: object, request_id: str
) -> ControlRequest:
    """Parse a JSON transport request into a typed control request."""
    args_type = _REQUEST_ARG_TYPES.get(command)
    if args_type is None:
        raise ControlError("invalid_command", f"Unknown command: {command}")
    try:
        typed_args = args_type.model_validate(args)
    except ValueError as exc:
        raise ControlError("invalid_argument", str(exc)) from exc
    _validate_request_args(command, typed_args)
    return ControlRequest(command=command, args=typed_args, request_id=request_id)


def _validate_request_args(command: str, args: CommandArgs) -> None:
    if (
        command == "playback.set"
        and isinstance(args, PlaybackStateArgs)
        and args.state not in {"playing", "paused"}
    ):
        raise ControlError("invalid_argument", "state must be playing or paused")
    if (
        command == "playback.mute"
        and isinstance(args, PlaybackStateArgs)
        and args.state not in {"muted", "unmuted"}
    ):
        raise ControlError("invalid_argument", "state must be muted or unmuted")


def parse_argv(argv: list[str]) -> Instruction:
    """Parse command-line arguments into a launch or send instruction."""
    args, wants_json = _strip_json(argv)
    if not args:
        return LaunchInstruction(path=None, json=wants_json)
    if args[0] == "--app-process":
        return AppProcessInstruction(path=Path(args[1]) if len(args) > 1 else None)
    if args[0] not in _KNOWN:
        if args[0].startswith("-"):
            return _fail(f"unknown option: {args[0]}")
        if len(args) > 1:
            return _fail("video launch accepts at most one path")
        return LaunchInstruction(path=Path(args[0]), json=wants_json)
    return SendInstruction(
        request=ControlRequest(
            command=_command_name(args),
            args=_command_args(args),
            request_id=str(uuid.uuid4()),
        ),
        json=wants_json,
    )


def _strip_json(argv: list[str]) -> tuple[list[str], bool]:
    wants_json = False
    result: list[str] = []
    for arg in argv:
        if arg == "--json":
            wants_json = True
        else:
            result.append(arg)
    return result, wants_json


def _command_name(args: list[str]) -> str:
    head = args[0]
    if head in {"ping", "state", "screenshot", "close"}:
        return f"session.{head}"
    if len(args) < 2:
        return _fail(f"{head} requires a subcommand")
    return f"{head}.{args[1]}"


def _command_args(args: list[str]) -> CommandArgs:
    head = args[0]
    if head in {"ping", "state", "close"}:
        _expect_len(args, 1)
        return NoArgs()
    if head == "screenshot":
        return _screenshot_args(args[1:])
    if head == "dialog":
        return _dialog_args(args[1:])
    if head == "file":
        return _file_args(args[1:])
    if head == "playback":
        return _playback_args(args[1:])
    if head == "trim":
        return _trim_args(args[1:])
    if head == "crop":
        return _crop_args(args[1:])
    if head == "split":
        return _split_args(args[1:])
    if head == "targets":
        return _targets_args(args[1:])
    if head == "quality":
        return _quality_args(args[1:])
    if head == "queue":
        return _queue_args(args[1:])
    if head == "render":
        return _render_args(args[1:])
    return _fail(f"unknown command: {head}")


def _screenshot_args(args: list[str]) -> ScreenshotArgs:
    values = _options(args, {"--output": "output", "--target": "target"})
    output = values.get("output")
    if output is not None and not isinstance(output, str):
        return _fail("screenshot --output must be a path")
    target = values.get("target", "window")
    if target not in {"window", "editor", "preview", "render"}:
        return _fail("--target must be one of window, editor, preview, render")
    target_value = cast(Literal["window", "editor", "preview", "render"], target)
    return ScreenshotArgs(
        output=Path(output) if output is not None else None,
        target=target_value,
    )


def _dialog_args(args: list[str]) -> NoArgs:
    if args == ["state"] or args == ["close"]:
        return NoArgs()
    if args == ["help", "open"]:
        return NoArgs()
    return _fail("dialog command must be state, close, or help open")


def _file_args(args: list[str]) -> PathArgs:
    if len(args) != 2 or args[0] != "open":
        return _fail("file command must be: file open PATH")
    return PathArgs(path=Path(args[1]))


def _playback_args(args: list[str]) -> PlaybackStateArgs | SecondsArgs | VolumeArgs:
    if len(args) < 1:
        return _fail("playback requires a subcommand")
    sub = args[0]
    if sub == "set":
        state = _required_option(args[1:], "--state")
        if state not in {"playing", "paused"}:
            return _fail("--state must be playing or paused")
        return PlaybackStateArgs(state=state)
    if sub == "seek":
        return SecondsArgs(seconds=_float_option(args[1:], "--seconds"))
    if sub == "volume":
        value = _int_option(args[1:], "--value")
        if value < 0 or value > 100:
            return _fail("--value must be between 0 and 100")
        return VolumeArgs(value=value)
    if sub == "mute":
        state = _required_option(args[1:], "--state")
        if state not in {"muted", "unmuted"}:
            return _fail("--state must be muted or unmuted")
        return PlaybackStateArgs(state=state)
    return _fail("unknown playback command")


def _trim_args(args: list[str]) -> TrimArgs:
    if not args or args[0] != "set":
        return _fail(
            "trim command must be: trim set [--start N|playhead] [--end N|playhead]"
        )
    values = _options(args[1:], {"--start": "start", "--end": "end"})
    if "start" not in values and "end" not in values:
        return _fail("trim set requires --start, --end, or both")
    return TrimArgs(
        start=_time_value(values["start"]) if "start" in values else None,
        end=_time_value(values["end"]) if "end" in values else None,
    )


def _crop_args(args: list[str]) -> CropArgs:
    if not args or args[0] != "set":
        _fail(
            "crop command must be: crop set --position top|bottom "
            "--x N --y N --w N --h N"
        )
    values = _options(
        args[1:],
        {"--position": "position", "--x": "x", "--y": "y", "--w": "w", "--h": "h"},
    )
    position = values.get("position")
    if position not in {"top", "bottom"}:
        return _fail("--position must be top or bottom")
    position_value = cast(Literal["top", "bottom"], position)
    return CropArgs(
        position=position_value,
        x=_float_value(values, "x"),
        y=_float_value(values, "y"),
        w=_float_value(values, "w"),
        h=_float_value(values, "h"),
    )


def _split_args(args: list[str]) -> SplitArgs | NoArgs:
    if args == ["flip"]:
        return NoArgs()
    if args and args[0] == "set":
        return SplitArgs(ratio=_float_option(args[1:], "--ratio"))
    return _fail("split command must be set or flip")


def _targets_args(args: list[str]) -> TargetsArgs | NoArgs:
    if args == ["list"]:
        return NoArgs()
    if len(args) >= 2 and args[0] == "set":
        return TargetsArgs(targets=tuple(args[1:]))
    return _fail("targets command must be list or set platform:format [...]")


def _quality_args(args: list[str]) -> QualityArgs:
    if not args or args[0] != "set":
        return _fail("quality command must be: quality set --value max|optimized")
    value = _required_option(args[1:], "--value")
    if value not in {"max", "optimized"}:
        return _fail("--value must be max or optimized")
    return QualityArgs(value=cast(Literal["max", "optimized"], value))


def _queue_args(args: list[str]) -> OutputArgs | QueueIndexArgs | NoArgs:
    if not args:
        return _fail("queue requires a subcommand")
    sub = args[0]
    if sub == "add":
        return _output_args(args[1:])
    if sub == "list" or sub == "render":
        _expect_len(args, 1)
        return NoArgs()
    if sub in {"remove", "edit"}:
        return QueueIndexArgs(index=_int_option(args[1:], "--index"))
    return _fail("unknown queue command")


def _render_args(args: list[str]) -> OutputArgs | NoArgs:
    if not args:
        return _fail("render requires a subcommand")
    sub = args[0]
    if sub == "start":
        return _output_args(args[1:])
    if sub == "stop" or sub == "status":
        _expect_len(args, 1)
        return NoArgs()
    return _fail("unknown render command")


def _output_args(args: list[str]) -> OutputArgs:
    values = _options(args, {"--output": "output", "--output-dir": "output_dir"})
    if ("output" in values) == ("output_dir" in values):
        return _fail("provide exactly one of --output or --output-dir")
    output = values.get("output")
    output_dir = values.get("output_dir")
    return OutputArgs(
        output=Path(output) if isinstance(output, str) else None,
        output_dir=Path(output_dir) if isinstance(output_dir, str) else None,
    )


def _options(args: list[str], names: dict[str, str]) -> JsonMap:
    values: JsonMap = {}
    index = 0
    while index < len(args):
        name = args[index]
        key = names.get(name)
        if key is None:
            return _fail(f"unknown option: {name}")
        if index + 1 >= len(args):
            return _fail(f"{name} requires a value")
        if key in values:
            return _fail(f"{name} was provided more than once")
        values[key] = args[index + 1]
        index += 2
    return values


def _required_option(args: list[str], name: str) -> str:
    values = _options(args, {name: name.removeprefix("--").replace("-", "_")})
    value = next(iter(values.values()), None)
    if not isinstance(value, str):
        return _fail(f"{name} is required")
    return value


def _float_option(args: list[str], name: str) -> float:
    return _float(_required_option(args, name), name)


def _int_option(args: list[str], name: str) -> int:
    raw = _required_option(args, name)
    try:
        return int(raw)
    except ValueError:
        return _fail(f"{name} must be an integer")


def _float_value(values: JsonMap, key: str) -> float:
    value = values.get(key)
    if not isinstance(value, str):
        return _fail(f"--{key} is required")
    return _float(value, f"--{key}")


def _time_value(value: object) -> float | str:
    if value == "playhead":
        return "playhead"
    if not isinstance(value, str):
        return _fail("trim value must be a number or playhead")
    return _float(value, "trim value")


def _float(raw: str, label: str) -> float:
    try:
        return float(raw)
    except ValueError:
        return _fail(f"{label} must be a number")


def _expect_len(args: list[str], length: int) -> None:
    if len(args) != length:
        return _fail("unexpected extra arguments")
    return None


def _fail(message: str) -> NoReturn:
    raise ControlError("invalid_argument", message)
