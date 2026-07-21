"""Tests for the always-on CLI control layer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import trimmy.__main__ as cli_module
from trimmy.apps.cli.application import parser as parser_module
from trimmy.apps.cli.application.dispatcher import COMMANDS, dispatch
from trimmy.apps.cli.application.formatter import human_text, json_text
from trimmy.apps.cli.application.parser import parse_argv, parse_request_payload
from trimmy.apps.cli.application.service import handle_request
from trimmy.apps.cli.domain.models import (
    AppProcessInstruction,
    CommandArgs,
    ControlError,
    ControlRequest,
    ControlResponse,
    CropArgs,
    LaunchInstruction,
    NoArgs,
    OutputArgs,
    PathArgs,
    Payload,
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


class FakeApp:
    """Records dispatcher calls and returns simple payloads."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.fail = False

    def _record(self, name: str, *args: object) -> Payload:
        self.calls.append((name, args))
        if self.fail:
            raise ControlError(
                "invalid_argument",
                "failed",
                Payload(data={"name": name}),
            )
        return Payload(data={"message": name, "args": [str(arg) for arg in args]})

    def ping(self):
        return self._record("ping")

    def state(self):
        return Payload(
            data={
                "view": "editor",
                "source_path": "video.mp4",
                "render": {"status": "idle"},
            }
        )

    def screenshot(self, output: Path | None, target: str):
        return self._record("screenshot", output, target)

    def close(self):
        return self._record("close")

    def dialog_state(self):
        return self._record("dialog_state")

    def dialog_close(self):
        return self._record("dialog_close")

    def dialog_help_open(self):
        return self._record("dialog_help_open")

    def file_open(self, path: Path):
        return self._record("file_open", path)

    def playback_set(self, state: str):
        return self._record("playback_set", state)

    def playback_seek(self, seconds: float):
        return self._record("playback_seek", seconds)

    def playback_volume(self, value: int):
        return self._record("playback_volume", value)

    def playback_mute(self, state: str):
        return self._record("playback_mute", state)

    def trim_set(self, start: float | str | None, end: float | str | None):
        return self._record("trim_set", start, end)

    def crop_set(self, position: str, x: float, y: float, w: float, h: float):
        return self._record("crop_set", position, x, y, w, h)

    def split_set(self, ratio: float):
        return self._record("split_set", ratio)

    def split_flip(self):
        return self._record("split_flip")

    def targets_set(self, targets: tuple[str, ...]):
        return self._record("targets_set", targets)

    def targets_list(self):
        return self._record("targets_list")

    def quality_set(self, value: str):
        return self._record("quality_set", value)

    def queue_add(self, output: Path | None, output_dir: Path | None):
        return self._record("queue_add", output, output_dir)

    def queue_list(self):
        return self._record("queue_list")

    def queue_remove(self, index: int):
        return self._record("queue_remove", index)

    def queue_edit(self, index: int):
        return self._record("queue_edit", index)

    def queue_render(self):
        return self._record("queue_render")

    def render_start(self, output: Path | None, output_dir: Path | None):
        return self._record("render_start", output, output_dir)

    def render_stop(self):
        return self._record("render_stop")

    def render_status(self):
        return self._record("render_status")


def request(command: str, args: CommandArgs | None = None) -> ControlRequest:
    """Build a typed request for dispatcher and service tests."""
    return ControlRequest(
        command=command,
        args=args if args is not None else NoArgs(),
        request_id="1",
    )


COMMAND_CASES = [
    (["ping"], "session.ping", NoArgs()),
    (["state"], "session.state", NoArgs()),
    (
        ["screenshot"],
        "session.screenshot",
        ScreenshotArgs(target="window"),
    ),
    (
        ["screenshot", "--target", "render"],
        "session.screenshot",
        ScreenshotArgs(target="render"),
    ),
    (
        ["screenshot", "--output", "shot.png", "--target", "preview"],
        "session.screenshot",
        ScreenshotArgs(output=Path("shot.png"), target="preview"),
    ),
    (["close"], "session.close", NoArgs()),
    (["dialog", "state"], "dialog.state", NoArgs()),
    (["dialog", "close"], "dialog.close", NoArgs()),
    (["dialog", "help", "open"], "dialog.help", NoArgs()),
    (["file", "open", "video.mp4"], "file.open", PathArgs(path=Path("video.mp4"))),
    (
        ["playback", "set", "--state", "playing"],
        "playback.set",
        PlaybackStateArgs(state="playing"),
    ),
    (
        ["playback", "seek", "--seconds", "4.5"],
        "playback.seek",
        SecondsArgs(seconds=4.5),
    ),
    (
        ["playback", "volume", "--value", "80"],
        "playback.volume",
        VolumeArgs(value=80),
    ),
    (
        ["playback", "mute", "--state", "muted"],
        "playback.mute",
        PlaybackStateArgs(state="muted"),
    ),
    (
        ["trim", "set", "--start", "playhead", "--end", "42.5"],
        "trim.set",
        TrimArgs(start="playhead", end=42.5),
    ),
    (
        ["trim", "set", "--start", "10"],
        "trim.set",
        TrimArgs(start=10.0),
    ),
    (
        [
            "crop",
            "set",
            "--position",
            "top",
            "--x",
            "1",
            "--y",
            "2",
            "--w",
            "3",
            "--h",
            "4",
        ],
        "crop.set",
        CropArgs(position="top", x=1.0, y=2.0, w=3.0, h=4.0),
    ),
    (["split", "set", "--ratio", "0.4"], "split.set", SplitArgs(ratio=0.4)),
    (["split", "flip"], "split.flip", NoArgs()),
    (
        ["targets", "set", "instagram:feed", "tiktok:video"],
        "targets.set",
        TargetsArgs(targets=("instagram:feed", "tiktok:video")),
    ),
    (["targets", "list"], "targets.list", NoArgs()),
    (
        ["quality", "set", "--value", "optimized"],
        "quality.set",
        QualityArgs(value="optimized"),
    ),
    (
        ["queue", "add", "--output", "out.mp4"],
        "queue.add",
        OutputArgs(output=Path("out.mp4")),
    ),
    (
        ["queue", "add", "--output-dir", "out"],
        "queue.add",
        OutputArgs(output_dir=Path("out")),
    ),
    (["queue", "list"], "queue.list", NoArgs()),
    (["queue", "remove", "--index", "2"], "queue.remove", QueueIndexArgs(index=2)),
    (["queue", "edit", "--index", "1"], "queue.edit", QueueIndexArgs(index=1)),
    (["queue", "render"], "queue.render", NoArgs()),
    (
        ["render", "start", "--output", "out.mp4"],
        "render.start",
        OutputArgs(output=Path("out.mp4")),
    ),
    (
        ["render", "start", "--output-dir", "out"],
        "render.start",
        OutputArgs(output_dir=Path("out")),
    ),
    (["render", "stop"], "render.stop", NoArgs()),
    (["render", "status"], "render.status", NoArgs()),
]


@pytest.mark.parametrize(
    ("argv", "command", "args"),
    COMMAND_CASES,
)
def test_parser_builds_command_envelopes(argv, command, args):
    instruction = parse_argv(argv)
    assert isinstance(instruction, SendInstruction)
    assert instruction.request.command == command
    assert instruction.request.args == args
    assert instruction.request.request_id


def test_parser_builds_launch_and_app_process_instructions():
    assert parse_argv([]) == LaunchInstruction(path=None, json=False)
    assert parse_argv(["--json"]) == LaunchInstruction(path=None, json=True)
    assert parse_argv(["movie.mp4"]) == LaunchInstruction(
        path=Path("movie.mp4"),
        json=False,
    )
    assert parse_argv(["movie.mp4", "--json"]) == LaunchInstruction(
        path=Path("movie.mp4"),
        json=True,
    )
    assert parse_argv(["--app-process"]) == AppProcessInstruction(path=None)
    assert parse_argv(["--app-process", "movie.mp4"]) == AppProcessInstruction(
        path=Path("movie.mp4")
    )


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--help"], "Launch Trimmy"),
        (["trim", "--help"], "Set trim bounds"),
        (["trim", "set", "--help"], "--start"),
        (["queue", "add", "--help"], "--output-dir"),
    ],
)
def test_typer_help_is_available_for_cli_commands(monkeypatch, args, expected):
    for name in dir(cli_module):
        if name.endswith("_cli"):
            monkeypatch.setattr(getattr(cli_module, name), "rich_markup_mode", None)
    result = CliRunner().invoke(
        cli_module._help_cli,
        args,
        color=False,
        prog_name="trimmy",
    )

    assert result.exit_code == 0
    assert expected in result.output


@pytest.mark.parametrize(
    "argv",
    [
        ["--bad"],
        ["a.mp4", "b.mp4"],
        ["dialog"],
        ["dialog", "bad"],
        ["file", "bad"],
        ["playback"],
        ["playback", "set", "--state", "bad"],
        ["playback", "seek", "--seconds", "x"],
        ["playback", "volume", "--value", "x"],
        ["playback", "volume", "--value", "101"],
        ["playback", "mute", "--state", "bad"],
        ["playback", "bad"],
        ["trim", "bad"],
        ["trim", "set"],
        ["trim", "set", "--start", "bad"],
        ["crop", "bad"],
        [
            "crop",
            "set",
            "--position",
            "middle",
            "--x",
            "1",
            "--y",
            "2",
            "--w",
            "3",
            "--h",
            "4",
        ],
        [
            "crop",
            "set",
            "--position",
            "top",
            "--x",
            "bad",
            "--y",
            "2",
            "--w",
            "3",
            "--h",
            "4",
        ],
        ["split", "bad"],
        ["split", "set"],
        ["targets", "bad"],
        ["targets", "set"],
        ["quality", "bad"],
        ["quality", "set", "--value", "bad"],
        ["queue"],
        ["queue", "bad"],
        ["queue", "list", "extra"],
        ["queue", "remove", "--index", "x"],
        ["queue", "add"],
        ["queue", "add", "--output", "a", "--output-dir", "b"],
        ["render"],
        ["render", "bad"],
        ["render", "stop", "extra"],
        ["screenshot", "--output", "a", "--target", "bad"],
        ["screenshot", "--bad", "a"],
        ["screenshot", "--output"],
        ["screenshot", "--output", "a", "--output", "b"],
    ],
)
def test_parser_rejects_invalid_commands(argv):
    with pytest.raises(ControlError) as excinfo:
        parse_argv(argv)
    assert excinfo.value.code == "invalid_argument"


@pytest.mark.parametrize(
    "call",
    [
        lambda: parser_module._command_args(["unknown"]),
        lambda: parser_module._playback_args([]),
        lambda: parser_module._queue_args([]),
        lambda: parser_module._render_args([]),
        lambda: _screenshot_args_with_non_string_output(),
        lambda: parser_module._float_value({}, "x"),
        lambda: parser_module._time_value([]),
    ],
)
def test_parser_private_defensive_errors_are_clear(call):
    with pytest.raises(ControlError):
        call()


def _screenshot_args_with_non_string_output():
    with patch.object(parser_module, "_options", return_value={"output": object()}):
        return parser_module._screenshot_args([])


@pytest.mark.parametrize(
    ("control_request", "call"),
    [
        (request("session.ping"), ("ping", ())),
        (request("session.state"), None),
        (
            request("session.screenshot", ScreenshotArgs()),
            ("screenshot", (None, "window")),
        ),
        (
            request("session.screenshot", ScreenshotArgs(output=Path("x.png"))),
            ("screenshot", (Path("x.png"), "window")),
        ),
        (request("session.close"), ("close", ())),
        (request("dialog.state"), ("dialog_state", ())),
        (request("dialog.close"), ("dialog_close", ())),
        (request("dialog.help"), ("dialog_help_open", ())),
        (
            request("file.open", PathArgs(path=Path("v.mp4"))),
            ("file_open", (Path("v.mp4"),)),
        ),
        (
            request("playback.set", PlaybackStateArgs(state="paused")),
            ("playback_set", ("paused",)),
        ),
        (
            request("playback.seek", SecondsArgs(seconds=3)),
            ("playback_seek", (3.0,)),
        ),
        (
            request("playback.volume", VolumeArgs(value=7)),
            ("playback_volume", (7,)),
        ),
        (
            request("playback.mute", PlaybackStateArgs(state="unmuted")),
            ("playback_mute", ("unmuted",)),
        ),
        (
            request("trim.set", TrimArgs(start=1, end="playhead")),
            ("trim_set", (1.0, "playhead")),
        ),
        (
            request("trim.set", TrimArgs(start=1)),
            ("trim_set", (1.0, None)),
        ),
        (
            request(
                "crop.set",
                CropArgs(position="bottom", x=1, y=2, w=3, h=4),
            ),
            ("crop_set", ("bottom", 1.0, 2.0, 3.0, 4.0)),
        ),
        (request("split.set", SplitArgs(ratio=0.6)), ("split_set", (0.6,))),
        (request("split.flip"), ("split_flip", ())),
        (
            request("targets.set", TargetsArgs(targets=("a:b",))),
            ("targets_set", (("a:b",),)),
        ),
        (request("targets.list"), ("targets_list", ())),
        (
            request("quality.set", QualityArgs(value="max")),
            ("quality_set", ("max",)),
        ),
        (
            request("queue.add", OutputArgs(output=Path("a.mp4"))),
            ("queue_add", (Path("a.mp4"), None)),
        ),
        (
            request("queue.add", OutputArgs(output_dir=Path("out"))),
            ("queue_add", (None, Path("out"))),
        ),
        (request("queue.list"), ("queue_list", ())),
        (request("queue.remove", QueueIndexArgs(index=1)), ("queue_remove", (1,))),
        (request("queue.edit", QueueIndexArgs(index=1)), ("queue_edit", (1,))),
        (request("queue.render"), ("queue_render", ())),
        (
            request("render.start", OutputArgs(output=Path("a.mp4"))),
            ("render_start", (Path("a.mp4"), None)),
        ),
        (
            request("render.start", OutputArgs(output_dir=Path("out"))),
            ("render_start", (None, Path("out"))),
        ),
        (request("render.stop"), ("render_stop", ())),
        (request("render.status"), ("render_status", ())),
    ],
)
def test_dispatch_calls_every_app_port_method(control_request, call):
    app = FakeApp()
    result = dispatch(control_request, app)
    assert result
    if call is not None:
        assert app.calls[-1] == call


def test_dispatch_registry_covers_parser_commands():
    parser_commands: set[str] = set()
    for argv, _command, _args in COMMAND_CASES:
        instruction = parse_argv(argv)
        assert isinstance(instruction, SendInstruction)
        parser_commands.add(instruction.request.command)
    assert parser_commands == set(COMMANDS)


def test_transport_parser_builds_typed_requests():
    parsed = parse_request_payload(
        "trim.set",
        {"start": "playhead", "end": 12.5},
        "abc",
    )
    assert parsed.command == "trim.set"
    assert parsed.args == TrimArgs(start="playhead", end=12.5)
    assert parsed.request_id == "abc"
    assert parsed.to_json() == {
        "command": "trim.set",
        "args": {"start": "playhead", "end": 12.5},
        "request_id": "abc",
    }


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("session.screenshot", {"output": 1}),
        ("session.screenshot", {"target": 1}),
        ("playback.seek", {"seconds": "x"}),
        ("playback.volume", {"value": "x"}),
        ("trim.set", {}),
        ("trim.set", {"start": "bad"}),
        ("queue.add", {"output": 1}),
        ("queue.add", {"output": "a.mp4", "output_dir": "out"}),
        ("playback.set", {"state": "muted"}),
        ("playback.mute", {"state": "playing"}),
        ("targets.set", {"targets": [1]}),
        ("missing", {}),
    ],
)
def test_transport_parser_rejects_invalid_payloads(command, args):
    with pytest.raises(ControlError):
        parse_request_payload(command, args, "1")


def test_dispatch_rejects_invalid_command_and_mismatched_args():
    with pytest.raises(ControlError):
        dispatch(request("missing"), FakeApp())
    with pytest.raises(ControlError):
        dispatch(request("session.screenshot", NoArgs()), FakeApp())


def test_service_wraps_success_with_state_and_errors_with_payloads():
    app = FakeApp()
    success = handle_request(request("session.ping"), app)
    assert success.ok is True
    assert success.state == app.state()

    state = handle_request(request("session.state"), app)
    assert state.result == app.state()
    assert state.state == app.state()

    app.fail = True
    failure = handle_request(request("session.ping"), app)
    assert failure.ok is False
    assert failure.error is not None
    assert failure.error.to_json() == {
        "code": "invalid_argument",
        "message": "failed",
        "details": {"name": "ping"},
    }


def test_response_models_and_formatters():
    ok = ControlResponse(
        ok=True,
        result=Payload(data={"message": "Done"}),
        state=Payload(data={"view": "editor"}),
    )
    assert ok.to_json() == {
        "ok": True,
        "result": {"message": "Done"},
        "state": {"view": "editor"},
    }
    assert human_text(ok) == "Done"
    assert json.loads(json_text(ok))["ok"] is True

    path = ControlResponse(ok=True, result=Payload(data={"path": "shot.png"}))
    assert human_text(path) == "shot.png"

    state = ControlResponse(
        ok=True,
        state=Payload(
            data={
                "view": "render",
                "source_path": None,
                "render": {"status": "running"},
            }
        ),
    )
    assert (
        human_text(state)
        == "Trimmy state: view=render, source=no video, render=running"
    )

    fallback = ControlResponse(ok=True)
    assert human_text(fallback) == "OK"

    error = ControlResponse(
        ok=False,
        error=ControlError("bad", "Nope").to_error(),
    )
    assert error.error is not None
    assert error.to_json()["error"] == error.error.to_json()
    assert human_text(error) == "Error [bad]: Nope"
    assert human_text(ControlResponse(ok=False)) == "Error [error]: Command failed"

    exc = ControlError("code", "message", Payload(data={"x": 1}))
    assert exc.to_error().to_json() == {
        "code": "code",
        "message": "message",
        "details": {"x": 1},
    }


def test_response_model_parses_transport_payload():
    response = ControlResponse.from_json(
        {
            "ok": False,
            "error": {"code": "bad", "message": "Nope", "details": {"x": 1}},
        }
    )
    assert response.error is not None
    assert response.error.to_json()["details"] == {"x": 1}
