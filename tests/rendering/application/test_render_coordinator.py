"""Tests for the render coordinator that wires the bus to the pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tests.mothers import make_spec
from trimmy.editing.trim.domain.models import TrimRange
from trimmy.rendering.application.coordinator import RenderCoordinator
from trimmy.rendering.application.render_segments_use_case import RenderSegmentsUseCase
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.messages import (
    RenderCompleted,
    RenderProgressed,
    RenderQueueCompleted,
    RenderQueueProgressed,
    StartRendering,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import ProcessResult, RenderQueueItem, RenderTarget
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.compat import override
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus


class _Backend(RenderingBackend):
    """Minimal backend returning canned encode results and recording cancels."""

    def __init__(self, results: list[ProcessResult | None]) -> None:
        self._results = list(results)
        self._cancelled = False
        self.cancel_calls = 0

    @property
    @override
    def cancelled(self) -> bool:
        return self._cancelled

    @override
    def cancel(self) -> None:
        self.cancel_calls += 1
        self._cancelled = True

    @override
    def detect_gpu_encoder(self) -> str | None:
        return None

    @override
    def run(
        self,
        command: Sequence[str],
        *,
        duration: float = 0.0,
        on_progress: object = None,
    ) -> ProcessResult | None:
        return self._results.pop(0)

    @override
    def output_size_mb(self, path: Path) -> float:
        return 5.0


def _coordinator(bus: InMemoryEventBus, backend: _Backend) -> RenderCoordinator:
    use_case = RenderSegmentsUseCase(InMemoryPresetRepository(), backend)
    return RenderCoordinator(bus, use_case, backend)


def test_start_rendering_publishes_completed():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, "")])
    _coordinator(bus, backend)

    completed: list[RenderCompleted] = []
    bus.subscribe(RenderCompleted, completed.append)

    bus.publish(StartRendering(make_spec()))

    assert len(completed) == 1
    assert completed[0].result.first.is_success


def test_start_rendering_publishes_progress_for_each_part():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, "")] * 3)
    _coordinator(bus, backend)

    progress: list[int] = []
    bus.subscribe(RenderProgressed, lambda event: progress.append(event.pct))

    bus.publish(StartRendering(make_spec(trim=TrimRange(0.0, 25.0)), max_duration=10))

    assert progress == [0, 33, 66]


def test_stop_rendering_cancels_the_backend():
    bus = InMemoryEventBus()
    backend = _Backend([])
    _coordinator(bus, backend)

    bus.publish(StopRendering())

    assert backend.cancel_calls == 1


def test_start_render_queue_publishes_progress_and_completed():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, ""), ProcessResult(0, "")])
    _coordinator(bus, backend)

    progress: list[RenderQueueProgressed] = []
    completed: list[RenderQueueCompleted] = []
    bus.subscribe(RenderQueueProgressed, progress.append)
    bus.subscribe(RenderQueueCompleted, completed.append)

    first = RenderTarget("instagram", "reels", "max")
    second = RenderTarget("twitter", "post", "max")
    bus.publish(
        StartRenderQueue(
            (
                RenderQueueItem(first, make_spec(platform="instagram"), None),
                RenderQueueItem(second, make_spec(platform="twitter"), None),
            ),
        ),
    )

    assert [event.target for event in progress if event.target_pct == 0] == [
        first,
        second,
    ]
    assert [event.item_index for event in progress if event.target_pct == 0] == [0, 1]
    assert progress[-1].global_pct == 100
    assert len(completed) == 1
    assert completed[0].result.parts == 2
