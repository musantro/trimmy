"""
Bridges the event bus to the render pipeline.

The coordinator is the rendering context's command handler: it subscribes to
``StartRendering``/``StopRendering`` and turns the render job into the
``RenderProgressed``/``RenderCompleted`` events the rest of the app reacts to.
It is deliberately synchronous and PySide6-free, so it can be driven by an
``InMemoryEventBus`` in tests; the GUI runs it behind a worker thread.
"""

from __future__ import annotations

from trimmy.rendering.application.render_queue_use_case import RenderQueueUseCase
from trimmy.rendering.application.render_segments_use_case import (
    RenderJobRequest,
    RenderSegmentsUseCase,
)
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.messages import (
    RenderCompleted,
    RenderProgressed,
    RenderQueueCompleted,
    RenderQueueProgressed,
    RetryFailedRendering,
    StartRendering,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import (
    RenderQueueResult,
    RenderTarget,
)
from trimmy.shared.domain.event_bus import EventBus


class RenderCoordinator:
    """Subscribes to render commands and republishes the job's outcome."""

    def __init__(
        self,
        bus: EventBus,
        render: RenderSegmentsUseCase,
        backend: RenderingBackend,
        queue: RenderQueueUseCase | None = None,
    ) -> None:
        self._bus = bus
        self._render = render
        self._backend = backend
        self._queue = queue or RenderQueueUseCase(render, backend)
        bus.subscribe(StartRendering, self._on_start)
        bus.subscribe(StartRenderQueue, self._on_start_queue)
        bus.subscribe(StopRendering, self._on_stop)
        bus.subscribe(RetryFailedRendering, self._on_retry)

    def _on_retry(self, command: RetryFailedRendering) -> None:
        previous = command.result
        if isinstance(previous, RenderQueueResult):
            items = tuple(entry.item for entry in previous.entries)
            if any(item is None for item in items):
                return
            result = self._queue.render(
                tuple(item for item in items if item is not None),
                previous=previous,
                on_progress=self._publish_queue_progress,
            )
            self._bus.publish(RenderQueueCompleted(result))
        else:
            spec = previous.first.spec
            if spec is None:
                return
            result = self._render.render(
                RenderJobRequest(
                    spec,
                    None,
                    self._publish_progress,
                    previous,
                    previous.target,
                )
            )
            self._bus.publish(RenderCompleted(result))

    def _on_start(self, command: StartRendering) -> None:
        """Render the requested spec, emitting progress then the outcome."""
        request = RenderJobRequest(
            spec=command.spec,
            max_duration=command.max_duration,
            target=command.target,
            on_progress=self._publish_progress,
        )
        result = self._render.render(request)
        self._bus.publish(RenderCompleted(result))

    def _on_start_queue(self, command: StartRenderQueue) -> None:
        """Render the queued targets, emitting per-target and global progress."""
        result = self._queue.render(
            command.items,
            on_progress=self._publish_queue_progress,
        )
        self._bus.publish(RenderQueueCompleted(result))

    def _on_stop(self, _command: StopRendering) -> None:
        """Cancel the in-flight encode."""
        self._backend.cancel()

    def _publish_progress(self, pct: int) -> None:
        self._bus.publish(RenderProgressed(pct))

    def _publish_queue_progress(
        self,
        item_index: int,
        target: RenderTarget,
        target_pct: int,
        global_pct: int,
    ) -> None:
        self._bus.publish(
            RenderQueueProgressed(item_index, target, target_pct, global_pct),
        )
