"""Qt local-socket server for Trimmy control commands."""

from __future__ import annotations

import json
from typing import Any, cast

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from trimmy.apps.cli.application.parser import parse_request_payload
from trimmy.apps.cli.application.service import handle_request
from trimmy.apps.desktop.control_adapter import MainWindowControlAdapter

SERVER_NAME = "trimmy-control"


class ControlServer:
    """Serve control requests for a main window."""

    def __init__(self, window: Any, name: str = SERVER_NAME) -> None:
        self._server = QLocalServer(window)
        self._adapter = MainWindowControlAdapter(window)
        self._server.newConnection.connect(self._on_connection)
        QLocalServer.removeServer(name)
        self._server.listen(name)

    def _on_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readyRead.connect(lambda sock=socket: self._on_ready(sock))

    def _on_ready(self, socket: QLocalSocket) -> None:
        payload = bytes(cast(Any, socket.readAll())).decode("utf-8")
        try:
            data = json.loads(payload)
            request = parse_request_payload(
                data["command"],
                data.get("args", {}),
                data.get("request_id", ""),
            )
            response = handle_request(request, self._adapter).to_json()
        except Exception as exc:
            response = {
                "ok": False,
                "error": {
                    "code": "invalid_command",
                    "message": str(exc),
                    "details": {},
                },
            }
        socket.write(QByteArray(json.dumps(response).encode("utf-8")))
        socket.flush()
        socket.disconnectFromServer()
