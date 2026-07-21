"""Client and launcher helpers for the Trimmy control socket."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from PySide6.QtNetwork import QLocalSocket

from trimmy.apps.cli.application.parser import parse_request_payload
from trimmy.apps.cli.domain.models import (
    ControlError,
    ControlRequest,
    ControlResponse,
    NoArgs,
    PathArgs,
    Payload,
)
from trimmy.apps.desktop.control_server import SERVER_NAME

_CONNECT_TIMEOUT_MS = 250


def send_request(
    request: ControlRequest, *, server_name: str = SERVER_NAME
) -> ControlResponse:
    """Send *request* to the running app."""
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        raise ControlError("app_unavailable", "Trimmy is not running")
    socket.write(json.dumps(request.to_json()).encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
    if not socket.waitForReadyRead(5000):
        raise ControlError("app_unavailable", "Trimmy did not respond")
    data = json.loads(bytes(cast(Any, socket.readAll())).decode("utf-8"))
    return ControlResponse.from_json(data)


def is_running() -> bool:
    """Return whether a default Trimmy control server is reachable."""
    try:
        send_request(
            ControlRequest(command="session.ping", args=NoArgs(), request_id="probe")
        )
    except ControlError:
        return False
    return True


def launch_app(path: Path | None, *, timeout: float = 10.0) -> ControlResponse:
    """Launch the app process and wait for the control socket."""
    if is_running():
        if path is not None:
            return send_request(
                ControlRequest(
                    command="file.open",
                    args=PathArgs(path=path),
                    request_id="open-after-running",
                ),
            )
        return ControlResponse(
            ok=True,
            result=Payload(data={"message": "Trimmy is already running"}),
            state=send_request(
                parse_request_payload("session.state", {}, "state")
            ).result,
        )

    cmd = [sys.executable, "-m", "trimmy", "--app-process"]
    if path is not None:
        cmd.append(str(path))
    try:
        subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise ControlError("launch_failed", f"Could not launch Trimmy: {exc}") from exc

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running():
            return ControlResponse(
                ok=True,
                result=Payload(data={"message": "Trimmy launched"}),
                state=send_request(
                    parse_request_payload("session.state", {}, "state")
                ).result,
            )
        time.sleep(0.05)
    raise ControlError("launch_timeout", "Timed out waiting for Trimmy to launch")
