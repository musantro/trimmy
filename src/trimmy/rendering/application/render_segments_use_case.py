"""Use case that renders a spec as one or more capped segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from trimmy.editing.shared.domain.models import TrimRange
from trimmy.rendering.application.render_video_use_case import RenderVideoUseCase
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.models import RenderJobResult, RenderOutcome, RenderSpec
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.rendering.domain.services import SegmentPlanner
from trimmy.shared.domain.use_case import UseCase

ProgressListener = Callable[[int, int], None]


@dataclass(frozen=True)
class RenderJobRequest:
    """Request to render a spec, splitting it by *max_duration*."""

    spec: RenderSpec
    max_duration: float | None
    on_progress: ProgressListener | None = None


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
        segments = self._planner.plan(request.spec.trim, request.max_duration)
        if len(segments) == 1:
            outcome = self._render.render(request.spec)
            return RenderJobResult(outcomes=(outcome,), multipart=False)

        outcomes: list[RenderOutcome] = []
        for segment in segments:
            if self._backend.cancelled:
                outcomes.append(RenderOutcome.cancelled())
                break
            if request.on_progress is not None:
                request.on_progress(segment.index, segment.total)
            seg_path = self._segment_path(request.spec.output_path, segment.index)
            seg_spec = replace(
                request.spec,
                trim=TrimRange(segment.start, segment.end),
                output_path=seg_path,
            )
            outcome = replace(
                self._render.render(seg_spec),
                index=segment.index,
                total=segment.total,
                path=str(seg_path),
            )
            outcomes.append(outcome)
            if not outcome.is_success:
                break
        return RenderJobResult(outcomes=tuple(outcomes), multipart=True)

    @staticmethod
    def _segment_path(output_path: Path, index: int) -> Path:
        """Return the part file path for segment *index*."""
        return output_path.parent / f"{output_path.stem}_part{index}.mp4"
