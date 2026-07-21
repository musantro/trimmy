"""Human and JSON formatting for control responses."""

from __future__ import annotations

import json

from trimmy.apps.cli.domain.models import ControlResponse, JsonMap, Payload


def json_text(response: ControlResponse) -> str:
    """Return a JSON response line."""
    return json.dumps(response.to_json(), sort_keys=True)


def human_text(response: ControlResponse) -> str:
    """Return a compact human-readable response."""
    if not response.ok:
        message = response.error.message if response.error else "Command failed"
        code = response.error.code if response.error else "error"
        return f"Error [{code}]: {message}"
    result = response.result.to_json()
    if "message" in result:
        return str(result["message"])
    if "path" in result:
        return str(result["path"])
    if response.state is not None:
        return _state_summary(response.state)
    return "OK"


def _state_summary(state: Payload) -> str:
    data: JsonMap = state.to_json()
    view = data.get("view", "unknown")
    source = data.get("source_path") or "no video"
    render = data.get("render")
    render_status = ""
    if isinstance(render, dict):
        render_status = f", render={render.get('status', 'idle')}"
    return f"Trimmy state: view={view}, source={source}{render_status}"
