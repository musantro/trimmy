"""Request handling helpers for the control server."""

from __future__ import annotations

from trimmy.control.application.dispatcher import dispatch
from trimmy.control.domain.models import (
    AppPort,
    ControlError,
    ControlRequest,
    ControlResponse,
)


def handle_request(request: ControlRequest, app: AppPort) -> ControlResponse:
    """Handle a control request and convert failures into response payloads."""
    try:
        result = dispatch(request, app)
        state = app.state() if request.command != "session.state" else result
        return ControlResponse(ok=True, result=result, state=state)
    except ControlError as exc:
        return ControlResponse(ok=False, error=exc.to_error())
