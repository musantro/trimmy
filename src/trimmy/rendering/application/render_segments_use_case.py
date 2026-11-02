"""Use case that renders a spec as one or more capped segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from trimmy.editing.trim.domain import TrimRange
from trimmy.rendering.application.render_video_use_case import RenderVideoUseCase
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.models import (
    RenderJobResult,
    RenderOutcome,
    RenderSpec,
    RenderStatus,
    RenderTarget,
    Segment,
)
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.rendering.domain.services import SegmentPlanner, segment_output_path
from trimmy.shared.domain.use_case import UseCase

ProgressListener = Callable[[int], None]


@dataclass(frozen=True)
class RenderJobRequest:
    """Request to render a spec, splitting it by *max_duration*."""

    spec: RenderSpec
    max_duration: float | None
    on_progress: ProgressListener | None = None
    previous: RenderJobResult | None = None
    target: RenderTarget | None = None


class RenderSegmentsUseCase(UseCase[RenderJobRequest, RenderJobResult]):
    """Renders a spec as one or more segments capped by max duration."""

    def __init__(
        self,
        preset_repository: PresetRepository,
        backend: RenderingBackend,
        planner: SegmentPlanner | None = None,
        render_use_case: RenderVideoUseCase | None = None,
    ) -> None:
        self._backend = backend
        self._planner = planner or SegmentPlanner()
        self._render = render_use_case or RenderVideoUseCase(
            preset_repository,
            backend,
        )

    def render(self, request: RenderJobRequest) -> RenderJobResult:
        """Plan the segments, render each and return the aggregate result."""
        segments = (
            [
                Segment(o.index, o.total, o.spec.trim.start, o.spec.trim.end)
                for o in request.previous.outcomes
                if o.spec is not None
            ]
            if request.previous is not None
            else self._planner.plan(request.spec.trim, request.max_duration)
        )
        outcomes: list[RenderOutcome] = []
        stopped = self._backend.cancelled
        for segment in segments:
            previous = (
                request.previous.outcomes[segment.index - 1]
                if request.previous is not None
                else None
            )
            if previous is not None and not previous.is_failed:
                outcomes.append(previous)
                continue

            seg_cb: ProgressListener | None = (
                request.on_progress if len(segments) == 1 else None
            )
            listener = request.on_progress
            if listener is not None and len(segments) > 1:
                base_pct = int((segment.index - 1) / segment.total * 100)
                listener(base_pct)

                def seg_cb(
                    ffmpeg_pct: int,
                    _base: int = base_pct,
                    _total: int = segment.total,
                    _cb: ProgressListener = listener,
                ) -> None:
                    _cb(int(_base + ffmpeg_pct / _total))

            seg_path = (
                self._segment_path(request.spec.output_path, segment.index)
                if len(segments) > 1
                else request.spec.output_path
            )
            seg_spec = replace(
                request.spec,
                trim=TrimRange(segment.start, segment.end),
                output_path=seg_path,
            )
            seg_spec = previous.spec if previous is not None else seg_spec
            assert seg_spec is not None  # noqa: S101
            if stopped or self._backend.cancelled:
                outcome = previous or RenderOutcome(status=RenderStatus.UNATTEMPTED)
            else:
                outcome = self._render.render(seg_spec, on_progress=seg_cb)
                stopped = outcome.is_cancelled or self._backend.cancelled
                if outcome.is_cancelled:
                    self._backend.cancel()
            outcome = replace(
                outcome,
                index=segment.index,
                total=segment.total,
                path=str(seg_spec.output_path),
                spec=seg_spec,
                cut_spec=previous.cut_spec if previous else request.spec,
            )
            outcomes.append(outcome)
        return RenderJobResult(
            outcomes=tuple(outcomes),
            multipart=len(segments) > 1,
            cancelled=stopped,
            target=request.target,
        )

    @staticmethod
    def _segment_path(output_path: Path, index: int) -> Path:
        """Return the part file path for segment *index*."""
        return segment_output_path(output_path, index)
