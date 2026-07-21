"""Entry point for the Trimmy application and control CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from trimmy.apps.cli.application.formatter import human_text, json_text
from trimmy.apps.cli.application.parser import parse_argv
from trimmy.apps.cli.domain.models import (
    AppProcessInstruction,
    ControlError,
    ControlResponse,
    LaunchInstruction,
    SendInstruction,
)

_help_cli = typer.Typer(
    add_completion=False,
    help=(
        "Launch Trimmy or control a running Trimmy app. "
        "Use `trimmy PATH` to open a video."
    ),
    no_args_is_help=False,
)
_dialog_cli = typer.Typer(add_completion=False, help="Control Trimmy dialogs.")
_dialog_help_cli = typer.Typer(add_completion=False, help="Control help dialogs.")
_file_cli = typer.Typer(add_completion=False, help="Open files in Trimmy.")
_playback_cli = typer.Typer(add_completion=False, help="Control playback.")
_trim_cli = typer.Typer(add_completion=False, help="Set trim bounds.")
_crop_cli = typer.Typer(add_completion=False, help="Set crop rectangles.")
_split_cli = typer.Typer(add_completion=False, help="Control split layout.")
_targets_cli = typer.Typer(add_completion=False, help="List or set render targets.")
_quality_cli = typer.Typer(add_completion=False, help="Set render quality.")
_queue_cli = typer.Typer(add_completion=False, help="Manage the render queue.")
_render_cli = typer.Typer(add_completion=False, help="Control rendering.")


@_help_cli.callback()
def _root_help(
    *,
    json: Annotated[  # noqa: A002
        bool,
        typer.Option("--json", help="Print command responses as JSON."),
    ] = False,
) -> None:
    """Launch Trimmy or send a control command."""


@_help_cli.command()
def ping() -> None:
    """Check whether a running Trimmy app is reachable."""


@_help_cli.command("state")
def session_state() -> None:
    """Print the current app state."""


@_help_cli.command()
def screenshot(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Path to save the screenshot."),
    ] = None,
    target: Annotated[
        str,
        typer.Option("--target", help="Target: window, editor, preview, or render."),
    ] = "window",
) -> None:
    """Capture a screenshot from the running app."""


@_help_cli.command("close")
def session_close() -> None:
    """Close the running Trimmy app."""


@_dialog_cli.command("state")
def dialog_state() -> None:
    """Print dialog state."""


@_dialog_cli.command("close")
def dialog_close() -> None:
    """Close the active dialog."""


@_dialog_help_cli.command("open")
def dialog_help_open() -> None:
    """Open the keyboard shortcuts help dialog."""


@_file_cli.command("open")
def file_open(
    path: Annotated[Path, typer.Argument(help="Video file to open.")],
) -> None:
    """Open a video in the running app."""


@_playback_cli.command("set")
def playback_set(
    state: Annotated[
        str,
        typer.Option("--state", help="Playback state: playing or paused."),
    ],
) -> None:
    """Set playback state."""


@_playback_cli.command("seek")
def playback_seek(
    seconds: Annotated[float, typer.Option("--seconds", help="Timeline position.")],
) -> None:
    """Seek playback to a timeline position."""


@_playback_cli.command("volume")
def playback_volume(
    value: Annotated[int, typer.Option("--value", help="Volume from 0 to 100.")],
) -> None:
    """Set playback volume."""


@_playback_cli.command("mute")
def playback_mute(
    state: Annotated[
        str,
        typer.Option("--state", help="Mute state: muted or unmuted."),
    ],
) -> None:
    """Set mute state."""


@_trim_cli.command("set")
def trim_set(
    start: Annotated[
        str | None,
        typer.Option("--start", help="Start time in seconds or playhead."),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", help="End time in seconds or playhead."),
    ] = None,
) -> None:
    """Set trim start, trim end, or both."""


@_crop_cli.command("set")
def crop_set(
    position: Annotated[
        str,
        typer.Option("--position", help="Crop position: top or bottom."),
    ],
    x: Annotated[float, typer.Option("--x", help="Crop x coordinate.")],
    y: Annotated[float, typer.Option("--y", help="Crop y coordinate.")],
    w: Annotated[float, typer.Option("--w", help="Crop width.")],
    h: Annotated[float, typer.Option("--h", help="Crop height.")],
) -> None:
    """Set one crop rectangle."""


@_split_cli.command("set")
def split_set(
    ratio: Annotated[float, typer.Option("--ratio", help="Split ratio.")],
) -> None:
    """Set the split ratio."""


@_split_cli.command("flip")
def split_flip() -> None:
    """Flip output areas."""


@_targets_cli.command("set")
def targets_set(
    targets: Annotated[
        list[str],
        typer.Argument(help="Targets such as instagram:reels or tiktok:video."),
    ],
) -> None:
    """Set render targets."""


@_targets_cli.command("list")
def targets_list() -> None:
    """List available render targets."""


@_quality_cli.command("set")
def quality_set(
    value: Annotated[
        str,
        typer.Option("--value", help="Quality: max or optimized."),
    ],
) -> None:
    """Set render quality."""


@_queue_cli.command("add")
def queue_add(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Output file path."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Output directory."),
    ] = None,
) -> None:
    """Add the current render to the queue."""


@_queue_cli.command("list")
def queue_list() -> None:
    """List queued renders."""


@_queue_cli.command("remove")
def queue_remove(
    index: Annotated[int, typer.Option("--index", help="Queue item index.")],
) -> None:
    """Remove a queued render."""


@_queue_cli.command("edit")
def queue_edit(
    index: Annotated[int, typer.Option("--index", help="Queue item index.")],
) -> None:
    """Edit a queued render."""


@_queue_cli.command("render")
def queue_render() -> None:
    """Render the queue."""


@_render_cli.command("start")
def render_start(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Output file path."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Output directory."),
    ] = None,
) -> None:
    """Start rendering immediately."""


@_render_cli.command("stop")
def render_stop() -> None:
    """Stop the active render."""


@_render_cli.command("status")
def render_status() -> None:
    """Print render status."""


_dialog_cli.add_typer(_dialog_help_cli, name="help")
_help_cli.add_typer(_dialog_cli, name="dialog")
_help_cli.add_typer(_file_cli, name="file")
_help_cli.add_typer(_playback_cli, name="playback")
_help_cli.add_typer(_trim_cli, name="trim")
_help_cli.add_typer(_crop_cli, name="crop")
_help_cli.add_typer(_split_cli, name="split")
_help_cli.add_typer(_targets_cli, name="targets")
_help_cli.add_typer(_quality_cli, name="quality")
_help_cli.add_typer(_queue_cli, name="queue")
_help_cli.add_typer(_render_cli, name="render")


def main() -> None:
    """Run the Trimmy launcher, app process, control command, or help command."""
    if "--help" in sys.argv[1:]:
        _help_cli()
        return
    try:
        instruction = parse_argv(sys.argv[1:])
        if isinstance(instruction, AppProcessInstruction):
            from trimmy.apps.desktop.bootstrap import run  # noqa: PLC0415

            run(str(instruction.path) if instruction.path is not None else None)
            return
        if isinstance(instruction, LaunchInstruction):
            from trimmy.apps.cli.control_client import launch_app  # noqa: PLC0415

            response = launch_app(instruction.path)
            _print_response(response, as_json=instruction.json)
            raise SystemExit(0)
        if isinstance(instruction, SendInstruction):
            from trimmy.apps.cli.control_client import send_request  # noqa: PLC0415

            response = send_request(instruction.request)
            _print_response(response, as_json=instruction.json)
            raise SystemExit(0 if response.ok else 1)
    except ControlError as exc:
        response = ControlResponse(ok=False, error=exc.to_error())
        _print_response(response, as_json="--json" in sys.argv[1:])
        raise SystemExit(1) from exc


def _print_response(response: ControlResponse, *, as_json: bool) -> None:
    text = json_text(response) if as_json else human_text(response)
    sys.stdout.write(f"{text}\n")


if __name__ == "__main__":
    main()
