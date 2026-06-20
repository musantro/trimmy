"""
Bridges the event bus to the render pipeline.

The coordinator is the rendering context's command handler: it subscribes to
``StartRendering``/``StopRendering`` and turns the render job into the
``RenderProgressed``/``RenderCompleted`` events the rest of the app reacts to.
It is deliberately synchronous and PySide6-free, so it can be driven by an
``InMemoryEventBus`` in tests; the GUI runs it behind a worker thread.
"""

from __future__ import annotations

from trimmy.rendering.application.render_segments_use_case import (
    RenderJobRequest,
    RenderSegmentsUseCase,
)
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.messages import (
    RenderCompleted,
    RenderProgressed,
    StartRendering,
    StopRendering,
)
from trimmy.shared.domain.event_bus import EventBus


class RenderCoordinator:
    """Subscribes to render commands and republishes the job's outcome."""

    def __init__(
        self,
        bus: EventBus,
        render: RenderSegmentsUseCase,
        backend: RenderingBackend,
    ) -> None:
        self._bus = bus
        self._render = render
        self._backend = backend
        bus.subscribe(StartRendering, self._on_start)
        bus.subscribe(StopRendering, self._on_stop)

    def _on_start(self, command: StartRendering) -> None:
        """Render the requested spec, emitting progress then the outcome."""
        request = RenderJobRequest(
            spec=command.spec,
            max_duration=command.max_duration,
            on_progress=self._publish_progress,
        )
        result = self._render.render(request)
        self._bus.publish(RenderCompleted(result))

    def _on_stop(self, _command: StopRendering) -> None:
        """Cancel the in-flight encode."""
        self._backend.cancel()

    def _publish_progress(self, pct: int) -> None:
        self._bus.publish(RenderProgressed(pct))
