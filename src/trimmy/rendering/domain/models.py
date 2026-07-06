"""Value objects describing a render job and its encoding parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trimmy.editing.shared.domain.models import CropSelection, TrimRange
from trimmy.shared.domain.aggregate_root import AggregateRoot

CANCELLED_MESSAGE = "Cancelled"


@dataclass(frozen=True)
class Segment:
    """One contiguous slice of the trim range produced for rendering."""

    index: int
    total: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        """Return the length of the segment in seconds."""
        return self.end - self.start

    @property
    def is_only(self) -> bool:
        """Return whether this segment is the whole, un-split range."""
        return self.total == 1


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
    audio_channels: int = 0
    audio_sample_rate: int = 0
    audio_codec: str = ""


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
class RenderTarget:
    """One selected platform/format/quality output target."""

    platform: str
    format_key: str
    quality: str

    @property
    def key(self) -> str:
        """Return a stable key for progress and filenames."""
        return f"{self.platform}_{self.format_key}_{self.quality}"


@dataclass(frozen=True)
class RenderQueueItem:
    """One queued render output with its split policy."""

    target: RenderTarget
    spec: RenderSpec
    max_duration: int | None


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


class RenderJobResult(AggregateRoot):
    """
    The aggregate result of a (possibly multi-part) render job.

    The outcomes are exposed through read-only properties, keeping the value
    semantics of the other rendering models, while the :class:`AggregateRoot`
    base lets the job record domain events.
    """

    def __init__(
        self,
        outcomes: tuple[RenderOutcome, ...],
        *,
        multipart: bool,
    ) -> None:
        super().__init__()
        self._outcomes = outcomes
        self._multipart = multipart

    @property
    def outcomes(self) -> tuple[RenderOutcome, ...]:
        """Return the per-part outcomes of the job."""
        return self._outcomes

    @property
    def multipart(self) -> bool:
        """Return whether the job was split into multiple parts."""
        return self._multipart

    @property
    def first(self) -> RenderOutcome:
        """Return the first outcome of the job."""
        return self._outcomes[0]

    @property
    def parts(self) -> int:
        """Return how many parts the job produced."""
        return len(self._outcomes)

    @property
    def is_cancelled(self) -> bool:
        """Return whether any part was cancelled."""
        return any(outcome.is_cancelled for outcome in self._outcomes)

    @property
    def failures(self) -> tuple[RenderOutcome, ...]:
        """Return the parts that failed for a non-cancel reason."""
        return tuple(o for o in self._outcomes if o.is_failed)

    @property
    def total_size_mb(self) -> float:
        """Return the combined size of all successful parts."""
        return round(
            sum(o.size_mb for o in self._outcomes if o.size_mb is not None),
            2,
        )


@dataclass(frozen=True)
class RenderQueueEntryResult:
    """The render result for one queued target."""

    target: RenderTarget
    result: RenderJobResult


class RenderQueueResult(AggregateRoot):
    """Aggregate result for a sequential multi-target render queue."""

    def __init__(self, entries: tuple[RenderQueueEntryResult, ...]) -> None:
        super().__init__()
        self._entries = entries

    @property
    def entries(self) -> tuple[RenderQueueEntryResult, ...]:
        """Return queued target results in render order."""
        return self._entries

    @property
    def parts(self) -> int:
        """Return the number of queued outputs that produced a result."""
        return len(self._entries)

    @property
    def is_cancelled(self) -> bool:
        """Return whether any queued render was cancelled."""
        return any(entry.result.is_cancelled for entry in self._entries)

    @property
    def failures(self) -> tuple[RenderQueueEntryResult, ...]:
        """Return queued outputs that have at least one non-cancel failure."""
        return tuple(entry for entry in self._entries if entry.result.failures)
