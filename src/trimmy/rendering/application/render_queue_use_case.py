"""Use case that renders multiple selected targets sequentially."""

from __future__ import annotations

from collections.abc import Callable

from trimmy.rendering.application.render_segments_use_case import (
    ProgressListener,
    RenderJobRequest,
    RenderSegmentsUseCase,
)
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.models import (
    RenderQueueEntryResult,
    RenderQueueItem,
    RenderQueueResult,
    RenderTarget,
)
from trimmy.shared.domain.use_case import UseCase

QueueProgressListener = Callable[[int, RenderTarget, int, int], None]


class RenderQueueUseCase(UseCase[tuple[RenderQueueItem, ...], RenderQueueResult]):
    """Renders queued outputs one after another through the segment renderer."""

    def __init__(
        self,
        render_segments: RenderSegmentsUseCase,
        backend: RenderingBackend,
    ) -> None:
        self._render_segments = render_segments
        self._backend = backend

    def render(
        self,
        items: tuple[RenderQueueItem, ...],
        *,
        on_progress: QueueProgressListener | None = None,
    ) -> RenderQueueResult:
        """Render each queued item and return the aggregate result."""
        if not items:
            return RenderQueueResult(entries=())

        entries: list[RenderQueueEntryResult] = []
        total = len(items)
        for index, item in enumerate(items):
            if self._backend.cancelled:
                break

            def progress_cb(
                pct: int,
                _index: int = index,
                _total: int = total,
                _target: RenderTarget = item.target,
                _listener: QueueProgressListener | None = on_progress,
            ) -> None:
                if _listener is None:
                    return
                target_pct = max(0, min(100, pct))
                global_pct = int(((_index * 100) + target_pct) / _total)
                _listener(_index, _target, target_pct, global_pct)

            listener: ProgressListener | None = progress_cb if on_progress else None
            progress_cb(0)
            result = self._render_segments.render(
                RenderJobRequest(
                    spec=item.spec,
                    max_duration=item.max_duration,
                    on_progress=listener,
                ),
            )
            entries.append(RenderQueueEntryResult(item.target, result))
            progress_cb(100)
            if result.failures or result.is_cancelled:
                break

        return RenderQueueResult(entries=tuple(entries))
