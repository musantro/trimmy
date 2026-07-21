"""CLI control contract value objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

JsonValue = Any
JsonMap = dict[str, JsonValue]
_TRIM_VALUE_ERROR = "trim values must be numbers or playhead"
_TRIM_BOUND_ERROR = "trim set requires start, end, or both"
_OUTPUT_ERROR = "provide exactly one of output or output_dir"


class ControlModel(BaseModel):
    """Base class for immutable control value objects."""

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
        extra="forbid",
    )


class NoArgs(ControlModel):
    """Command arguments for commands without user-supplied values."""


class ScreenshotArgs(ControlModel):
    """Screenshot command arguments."""

    output: Path | None = None
    target: Literal["window", "editor", "preview", "render"] = "window"


class PathArgs(ControlModel):
    """Command arguments carrying one filesystem path."""

    path: Path


class PlaybackStateArgs(ControlModel):
    """Playback state command arguments."""

    state: str


class SecondsArgs(ControlModel):
    """Command arguments carrying a seconds value."""

    seconds: float


class VolumeArgs(ControlModel):
    """Volume command arguments."""

    value: int = Field(ge=0, le=100)


class TrimArgs(ControlModel):
    """Trim command arguments."""

    start: float | str | None = None
    end: float | str | None = None

    @field_validator("start", "end")
    @classmethod
    def _validate_time(cls, value: float | str | None) -> float | str | None:
        if isinstance(value, str) and value != "playhead":
            raise ValueError(_TRIM_VALUE_ERROR)
        return value

    @model_validator(mode="after")
    def _require_bound(self) -> Self:
        if self.start is None and self.end is None:
            raise ValueError(_TRIM_BOUND_ERROR)
        return self


class CropArgs(ControlModel):
    """Crop rectangle command arguments."""

    position: Literal["top", "bottom"]
    x: float
    y: float
    w: float
    h: float


class SplitArgs(ControlModel):
    """Split ratio command arguments."""

    ratio: float = Field(gt=0, lt=1)


class TargetsArgs(ControlModel):
    """Target selection command arguments."""

    targets: tuple[str, ...] = Field(min_length=1)


class QualityArgs(ControlModel):
    """Quality preset command arguments."""

    value: Literal["max", "optimized"]


class OutputArgs(ControlModel):
    """Render output command arguments."""

    output: Path | None = None
    output_dir: Path | None = None

    @model_validator(mode="after")
    def _require_one_output(self) -> Self:
        if (self.output is None) == (self.output_dir is None):
            raise ValueError(_OUTPUT_ERROR)
        return self


class QueueIndexArgs(ControlModel):
    """Queue index command arguments."""

    index: int


CommandArgs = (
    NoArgs
    | ScreenshotArgs
    | PathArgs
    | PlaybackStateArgs
    | SecondsArgs
    | VolumeArgs
    | TrimArgs
    | CropArgs
    | SplitArgs
    | TargetsArgs
    | QualityArgs
    | OutputArgs
    | QueueIndexArgs
)


class Payload(ControlModel):
    """JSON-compatible result or state payload."""

    data: JsonMap = Field(default_factory=dict)

    def to_json(self) -> JsonMap:
        """Return the wrapped payload as a JSON-compatible mapping."""
        return self.data


class ErrorPayload(ControlModel):
    """User-facing control error payload."""

    code: str
    message: str
    details: Payload = Field(default_factory=Payload)

    def to_json(self) -> JsonMap:
        """Return the error as a JSON-compatible mapping."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details.to_json(),
        }


class ControlRequest(ControlModel):
    """A command sent to the running app."""

    command: str
    args: CommandArgs
    request_id: str

    def to_json(self) -> JsonMap:
        """Return the request as a JSON-compatible mapping."""
        return {
            "command": self.command,
            "args": self.args.model_dump(mode="json"),
            "request_id": self.request_id,
        }


class ControlResponse(ControlModel):
    """A command response returned by the running app."""

    ok: bool
    result: Payload = Field(default_factory=Payload)
    state: Payload | None = None
    error: ErrorPayload | None = None

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        """Parse a transport response into typed response objects."""
        error_payload = payload.get("error")
        error = None
        if isinstance(error_payload, dict):
            details = error_payload.get("details", {})
            error = ErrorPayload(
                code=str(error_payload.get("code", "error")),
                message=str(error_payload.get("message", "Command failed")),
                details=Payload(data=details if isinstance(details, dict) else {}),
            )
        state = payload.get("state")
        return cls(
            ok=bool(payload.get("ok")),
            result=Payload(
                data=payload["result"]
                if isinstance(payload.get("result"), dict)
                else {}
            ),
            state=Payload(data=state) if isinstance(state, dict) else None,
            error=error,
        )

    def to_json(self) -> JsonMap:
        """Return the response as a JSON-compatible object."""
        payload: JsonMap = {"ok": self.ok}
        if self.ok:
            payload["result"] = self.result.to_json()
            if self.state is not None:
                payload["state"] = self.state.to_json()
        else:
            payload["error"] = self.error.to_json() if self.error else {}
        return payload


class ControlError(Exception):
    """A user-facing control error with a stable code."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Payload | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or Payload()

    def to_error(self) -> ErrorPayload:
        """Return a typed error payload."""
        return ErrorPayload(
            code=self.code,
            message=self.message,
            details=self.details,
        )


@dataclass(frozen=True)
class LaunchInstruction:
    """Instruction to launch the GUI process."""

    path: Path | None
    json: bool


@dataclass(frozen=True)
class AppProcessInstruction:
    """Instruction to run the actual Qt app process."""

    path: Path | None


@dataclass(frozen=True)
class SendInstruction:
    """Instruction to send a request to the running app."""

    request: ControlRequest
    json: bool


Instruction = LaunchInstruction | AppProcessInstruction | SendInstruction


class AppPort(Protocol):
    """Behavior required by the command dispatcher."""

    def ping(self) -> Payload: ...

    def state(self) -> Payload: ...

    def screenshot(self, output: Path | None, target: str) -> Payload: ...

    def close(self) -> Payload: ...

    def dialog_state(self) -> Payload: ...

    def dialog_close(self) -> Payload: ...

    def dialog_help_open(self) -> Payload: ...

    def file_open(self, path: Path) -> Payload: ...

    def playback_set(self, state: str) -> Payload: ...

    def playback_seek(self, seconds: float) -> Payload: ...

    def playback_volume(self, value: int) -> Payload: ...

    def playback_mute(self, state: str) -> Payload: ...

    def trim_set(
        self, start: float | str | None, end: float | str | None
    ) -> Payload: ...

    def crop_set(
        self,
        position: str,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> Payload: ...

    def split_set(self, ratio: float) -> Payload: ...

    def split_flip(self) -> Payload: ...

    def targets_set(self, targets: tuple[str, ...]) -> Payload: ...

    def targets_list(self) -> Payload: ...

    def quality_set(self, value: str) -> Payload: ...

    def queue_add(self, output: Path | None, output_dir: Path | None) -> Payload: ...

    def queue_list(self) -> Payload: ...

    def queue_remove(self, index: int) -> Payload: ...

    def queue_edit(self, index: int) -> Payload: ...

    def queue_render(self) -> Payload: ...

    def render_start(self, output: Path | None, output_dir: Path | None) -> Payload: ...

    def render_stop(self) -> Payload: ...

    def render_status(self) -> Payload: ...
