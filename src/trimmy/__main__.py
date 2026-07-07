"""Entry point for the Trimmy application and control CLI."""

from __future__ import annotations

import sys

from trimmy.control.application.formatter import human_text, json_text
from trimmy.control.application.parser import parse_argv
from trimmy.control.domain.models import (
    AppProcessInstruction,
    ControlError,
    ControlResponse,
    LaunchInstruction,
    SendInstruction,
)


def main() -> None:
    """Run the Trimmy launcher, app process, or control command."""
    try:
        instruction = parse_argv(sys.argv[1:])
        if isinstance(instruction, AppProcessInstruction):
            from trimmy.app.main_window import run  # noqa: PLC0415

            run(str(instruction.path) if instruction.path is not None else None)
            return
        if isinstance(instruction, LaunchInstruction):
            from trimmy.app.control_client import launch_app  # noqa: PLC0415

            response = launch_app(instruction.path)
            _print_response(response, as_json=instruction.json)
            raise SystemExit(0)
        if isinstance(instruction, SendInstruction):
            from trimmy.app.control_client import send_request  # noqa: PLC0415

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
