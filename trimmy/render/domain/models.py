"""Value objects describing a render job and its encoding parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trimmy.crop.domain.models import CropSelection
from trimmy.trim.domain.models import TrimRange

CANCELLED_MESSAGE = "Cancelled"


@dataclass(frozen=True)
class Resolution:
    """Output frame dimensions in pixels."""

    width: int
    height: int

    @property
    def label(self) -> str:
        """Return the ``WIDTHxHEIGHT`` string used in result messages."""
        return f"{self.width}x{self.height}"


@dataclass(frozen=True)
class EncoderPreset:
    """All ffmpeg encoding parameters for one platform/quality pair."""

    width: int
    height: int
    profile: str
    level: str
    preset: str
    crf: int
    max_fps: int
    audio_bitrate: str
    max_size_mb: int
    movflags: str
    maxrate: str | None = None
    bufsize: str | None = None
    bufsize_mult: int | None = None

    @property
    def resolution(self) -> Resolution:
        """Return the output resolution of the preset."""
        return Resolution(self.width, self.height)


@dataclass(frozen=True)
class PlatformDisplayInfo:
    """Human-readable description of a platform/quality pair."""

    res: str
    codec: str
    bitrate: str
    max_fps: int
    audio: str
    max_size: str
    note: str


@dataclass(frozen=True)
class PlatformFormat:
    """A named upload format with an optional maximum duration."""

    key: str
    label: str
    max_duration: int | None


@dataclass(frozen=True)
class VideoMetadata:
    """Probed properties of a source video file."""

    duration: float
    width: int
    height: int
    fps: float


@dataclass(frozen=True)
class ProcessResult:
    """The exit code and captured stderr of an encoder invocation."""

    returncode: int
    stderr: str


@dataclass(frozen=True)
class DimensionPlan:
    """Even-aligned crop and output dimensions for the filter graph."""

    output_width: int
    top_x: int
    top_y: int
    top_w: int
    top_h: int
    top_out_h: int
    bottom_x: int
    bottom_y: int
    bottom_w: int
    bottom_h: int
    bottom_out_h: int


@dataclass(frozen=True)
class FpsPlan:
    """The fps filter suffix and resulting output frame rate."""

    filter_suffix: str
    output_fps: float


@dataclass(frozen=True)
class BitratePlan:
    """The resolved maxrate/bufsize pair for an encode."""

    maxrate: str
    bufsize: str


@dataclass(frozen=True)
class RenderSpec:
    """Everything needed to render one continuous output clip."""

    source_path: Path
    output_path: Path
    trim: TrimRange
    crops: CropSelection
    split_ratio: float
    platform: str
    quality: str
    source_fps: float


@dataclass(frozen=True)
class RenderOutcome:
    """The result of rendering a single clip or segment."""

    error: str | None = None
    size_mb: float | None = None
    resolution: str | None = None
    fps: float | None = None
    encoder: str | None = None
    index: int = 1
    total: int = 1
    path: str | None = None

    @classmethod
    def succeeded(
        cls,
        *,
        size_mb: float,
        resolution: str,
        fps: float,
        encoder: str,
    ) -> RenderOutcome:
        """Build a successful outcome."""
        return cls(
            size_mb=size_mb,
            resolution=resolution,
            fps=fps,
            encoder=encoder,
        )

    @classmethod
    def failed(cls, message: str) -> RenderOutcome:
        """Build a failed outcome carrying *message*."""
        return cls(error=message)

    @classmethod
    def cancelled(cls) -> RenderOutcome:
        """Build a cancelled outcome."""
        return cls(error=CANCELLED_MESSAGE)

    @property
    def is_cancelled(self) -> bool:
        """Return whether the render was cancelled."""
        return self.error == CANCELLED_MESSAGE

    @property
    def is_failed(self) -> bool:
        """Return whether the render failed for a non-cancel reason."""
        return self.error is not None and not self.is_cancelled

    @property
    def is_success(self) -> bool:
        """Return whether the render completed successfully."""
        return self.error is None


@dataclass(frozen=True)
class RenderJobResult:
    """The aggregate result of a (possibly multi-part) render job."""

    outcomes: tuple[RenderOutcome, ...]
    multipart: bool

    @property
    def first(self) -> RenderOutcome:
        """Return the first outcome of the job."""
        return self.outcomes[0]

    @property
    def parts(self) -> int:
        """Return how many parts the job produced."""
        return len(self.outcomes)

    @property
    def is_cancelled(self) -> bool:
        """Return whether any part was cancelled."""
        return any(outcome.is_cancelled for outcome in self.outcomes)

    @property
    def failures(self) -> tuple[RenderOutcome, ...]:
        """Return the parts that failed for a non-cancel reason."""
        return tuple(o for o in self.outcomes if o.is_failed)

    @property
    def total_size_mb(self) -> float:
        """Return the combined size of all successful parts."""
        return round(
            sum(o.size_mb for o in self.outcomes if o.size_mb is not None),
            2,
        )
