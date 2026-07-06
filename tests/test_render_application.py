"""Tests for the render application layer (use cases)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from tests.mothers import make_spec
from trimmy.editing.shared.domain.models import TrimRange
from trimmy.rendering.application.probe_video_use_case import (
    ProbeVideoRequest,
    ProbeVideoUseCase,
)
from trimmy.rendering.application.render_queue_use_case import RenderQueueUseCase
from trimmy.rendering.application.render_segments_use_case import (
    RenderJobRequest,
    RenderSegmentsUseCase,
)
from trimmy.rendering.application.render_video_use_case import RenderVideoUseCase
from trimmy.rendering.domain.gateways import RenderingBackend, VideoProber
from trimmy.rendering.domain.models import (
    ProcessResult,
    RenderQueueItem,
    RenderTarget,
    VideoMetadata,
)
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.compat import override


class FakeBackend(RenderingBackend):
    """Configurable in-memory rendering backend for tests."""

    def __init__(
        self,
        *,
        gpu_encoder: str | None = None,
        results: list[ProcessResult | None] | None = None,
        cancelled: bool = False,
        size_mb: float = 10.0,
        report_progress: int | None = None,
    ) -> None:
        self._gpu = gpu_encoder
        self._results = list(results or [])
        self._cancelled = cancelled
        self._size = size_mb
        self._report_progress = report_progress
        self.commands: list[list[str]] = []

    @property
    @override
    def cancelled(self) -> bool:
        return self._cancelled

    @override
    def cancel(self) -> None:
        self._cancelled = True

    @override
    def detect_gpu_encoder(self) -> str | None:
        return self._gpu

    @override
    def run(
        self,
        command: Sequence[str],
        *,
        duration: float = 0.0,
        on_progress: Callable[[int], None] | None = None,
    ) -> ProcessResult | None:
        self.commands.append(list(command))
        if on_progress is not None and self._report_progress is not None:
            on_progress(self._report_progress)
        return self._results.pop(0)

    @override
    def output_size_mb(self, path: Path) -> float:
        return self._size


class FakeProber(VideoProber):
    """Returns a fixed metadata object."""

    @override
    def probe(self, path: Path) -> VideoMetadata:
        return VideoMetadata(duration=12.0, width=1920, height=1080, fps=30.0)


def _presets() -> InMemoryPresetRepository:
    return InMemoryPresetRepository()


# ---- probe ----


def test_probe_video_use_case():
    metadata = ProbeVideoUseCase(FakeProber()).probe(
        ProbeVideoRequest(Path("clip.mp4")),
    )
    assert metadata.fps == 30.0
    assert metadata.width == 1920


# ---- single render ----


def test_render_cpu_success():
    backend = FakeBackend(results=[ProcessResult(0, "")], size_mb=8.0)
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.is_success
    assert outcome.encoder == "libx264"
    assert outcome.size_mb == 8.0
    assert outcome.resolution == "1080x1920"


def test_render_cpu_error():
    backend = FakeBackend(results=[ProcessResult(1, "encoding failure")])
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.is_failed
    assert outcome.error == "encoding failure"


def test_render_cpu_cancelled():
    backend = FakeBackend(results=[None])
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.is_cancelled


def test_render_gpu_success():
    backend = FakeBackend(
        gpu_encoder="h264_nvenc",
        results=[ProcessResult(0, "")],
    )
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.encoder == "h264_nvenc"
    assert outcome.is_success


def test_render_gpu_cancelled():
    backend = FakeBackend(gpu_encoder="h264_nvenc", results=[None])
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.is_cancelled


def test_render_gpu_failure_falls_back_to_cpu():
    backend = FakeBackend(
        gpu_encoder="h264_nvenc",
        results=[ProcessResult(1, "gpu boom"), ProcessResult(0, "")],
    )
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.encoder == "libx264"
    assert outcome.is_success
    assert len(backend.commands) == 2


def test_render_gpu_failure_then_cancelled():
    backend = FakeBackend(
        gpu_encoder="h264_nvenc",
        results=[ProcessResult(1, "gpu boom")],
        cancelled=True,
    )
    outcome = RenderVideoUseCase(_presets(), backend).render(make_spec())
    assert outcome.is_cancelled
    assert len(backend.commands) == 1


# ---- segmented render ----


def test_segments_single_part():
    backend = FakeBackend(results=[ProcessResult(0, "")])
    result = RenderSegmentsUseCase(_presets(), backend).render(
        RenderJobRequest(spec=make_spec(), max_duration=None),
    )
    assert result.multipart is False
    assert result.parts == 1
    assert result.first.is_success


def test_segments_multiple_parts_success():
    backend = FakeBackend(results=[ProcessResult(0, "")] * 3, size_mb=2.0)
    progress: list[int] = []
    spec = make_spec(trim=TrimRange(0.0, 25.0))
    result = RenderSegmentsUseCase(_presets(), backend).render(
        RenderJobRequest(
            spec=spec,
            max_duration=10.0,
            on_progress=progress.append,
        ),
    )
    assert result.multipart is True
    assert result.parts == 3
    assert result.total_size_mb == 6.0
    assert progress == [0, 33, 66]
    assert result.outcomes[0].path is not None
    assert result.outcomes[0].path.endswith("_part1.mp4")


def test_segments_multiple_parts_forwards_ffmpeg_progress():
    backend = FakeBackend(
        results=[ProcessResult(0, "")] * 3,
        report_progress=50,
    )
    progress: list[int] = []
    spec = make_spec(trim=TrimRange(0.0, 25.0))
    RenderSegmentsUseCase(_presets(), backend).render(
        RenderJobRequest(
            spec=spec,
            max_duration=10.0,
            on_progress=progress.append,
        ),
    )
    assert 0 in progress
    assert any(p > 0 for p in progress)


def test_segments_cancelled_before_first_part():
    backend = FakeBackend(cancelled=True)
    result = RenderSegmentsUseCase(_presets(), backend).render(
        RenderJobRequest(spec=make_spec(trim=TrimRange(0.0, 25.0)), max_duration=10.0),
    )
    assert result.is_cancelled
    assert backend.commands == []


def test_segments_failure_breaks_early():
    backend = FakeBackend(results=[ProcessResult(1, "bad part")])
    result = RenderSegmentsUseCase(_presets(), backend).render(
        RenderJobRequest(spec=make_spec(trim=TrimRange(0.0, 25.0)), max_duration=10.0),
    )
    assert result.failures
    assert result.parts == 1
    assert result.failures[0].index == 1


# ---- queued render ----


def _queue_item(platform: str, format_key: str = "post") -> RenderQueueItem:
    target = RenderTarget(platform=platform, format_key=format_key, quality="max")
    return RenderQueueItem(
        target=target,
        spec=make_spec(platform=platform),
        max_duration=None,
    )


def test_queue_renders_targets_in_order():
    backend = FakeBackend(results=[ProcessResult(0, ""), ProcessResult(0, "")])
    use_case = RenderQueueUseCase(RenderSegmentsUseCase(_presets(), backend), backend)

    result = use_case.render(
        (
            _queue_item("instagram", "reels"),
            _queue_item("twitter", "post"),
        ),
    )

    assert result.parts == 2
    assert [entry.target.platform for entry in result.entries] == [
        "instagram",
        "twitter",
    ]
    assert len(backend.commands) == 2


def test_queue_reports_global_progress_across_targets():
    backend = FakeBackend(
        results=[ProcessResult(0, ""), ProcessResult(0, "")],
        report_progress=50,
    )
    use_case = RenderQueueUseCase(RenderSegmentsUseCase(_presets(), backend), backend)
    progress: list[tuple[str, int, int]] = []

    use_case.render(
        (
            _queue_item("instagram", "reels"),
            _queue_item("twitter", "post"),
        ),
        on_progress=lambda target, pct, global_pct: progress.append(
            (target.platform, pct, global_pct),
        ),
    )

    assert ("instagram", 0, 0) in progress
    assert ("instagram", 50, 25) in progress
    assert ("instagram", 100, 50) in progress
    assert ("twitter", 50, 75) in progress
    assert progress[-1] == ("twitter", 100, 100)


def test_queue_stops_after_failure():
    backend = FakeBackend(results=[ProcessResult(1, "bad"), ProcessResult(0, "")])
    use_case = RenderQueueUseCase(RenderSegmentsUseCase(_presets(), backend), backend)

    result = use_case.render(
        (
            _queue_item("instagram", "reels"),
            _queue_item("twitter", "post"),
        ),
    )

    assert result.failures
    assert result.parts == 1
    assert len(backend.commands) == 1
