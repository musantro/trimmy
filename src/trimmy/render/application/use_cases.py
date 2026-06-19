"""Use cases that probe sources and orchestrate the render pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from trimmy.render.domain.gateways import RenderingBackend, VideoProber
from trimmy.render.domain.models import (
    RenderJobResult,
    RenderOutcome,
    RenderSpec,
    VideoMetadata,
)
from trimmy.render.domain.preset_repository import PresetRepository
from trimmy.render.domain.services import (
    BitratePlanner,
    CodecArgsFactory,
    CommandBuilder,
    DimensionPlanner,
    FilterGraphBuilder,
    FpsPlanner,
)
from trimmy.shared.compat import override
from trimmy.shared.domain.use_case import UseCase
from trimmy.trim.domain.models import TrimRange
from trimmy.trim.domain.services import SegmentPlanner

logger = logging.getLogger(__name__)

ProgressListener = Callable[[int, int], None]

_GPU_STDERR_TAIL = 500
_CPU_STDERR_TAIL = 2000


@dataclass(frozen=True)
class ProbeVideoRequest:
    """Request to probe the metadata of a source file."""

    path: Path


class ProbeVideoUseCase(UseCase[ProbeVideoRequest, VideoMetadata]):
    """Reads metadata from a source video via the prober gateway."""

    def __init__(self, prober: VideoProber) -> None:
        self._prober = prober

    @override
    def execute(self, request: ProbeVideoRequest) -> VideoMetadata:
        """Return the probed metadata for the requested path."""
        return self._prober.probe(request.path)


class RenderVideoUseCase(UseCase[RenderSpec, RenderOutcome]):
    """Renders a single continuous clip, trying GPU then CPU encoding."""

    def __init__(
        self,
        preset_repository: PresetRepository,
        backend: RenderingBackend,
    ) -> None:
        self._presets = preset_repository
        self._backend = backend
        self._dimensions = DimensionPlanner()
        self._fps = FpsPlanner()
        self._filters = FilterGraphBuilder()
        self._bitrate = BitratePlanner()
        self._codecs = CodecArgsFactory()
        self._commands = CommandBuilder()

    @override
    def execute(self, request: RenderSpec) -> RenderOutcome:
        """Render *request* and return the outcome."""
        preset = self._presets.encoder_preset(request.platform, request.quality)
        dimensions = self._dimensions.plan(
            request.crops,
            request.split_ratio,
            preset,
        )
        fps = self._fps.plan(request.source_fps, preset)
        filter_complex = self._filters.build(dimensions, fps.filter_suffix)
        bitrate = self._bitrate.plan(preset, request.trim.duration)
        resolution = preset.resolution.label

        gpu_encoder = self._backend.detect_gpu_encoder()
        if gpu_encoder is not None:
            gpu_args = self._codecs.gpu(gpu_encoder, preset)
            if gpu_args is not None:
                command = self._commands.build(
                    request,
                    preset,
                    filter_complex,
                    gpu_args,
                    bitrate,
                    gpu=True,
                )
                result = self._backend.run(command)
                if result is None:
                    return RenderOutcome.cancelled()
                if result.returncode == 0:
                    return RenderOutcome.succeeded(
                        size_mb=self._backend.output_size_mb(
                            request.output_path,
                        ),
                        resolution=resolution,
                        fps=fps.output_fps,
                        encoder=gpu_encoder,
                    )
                logger.warning(
                    "GPU encode failed (%s), falling back to libx264: %s",
                    gpu_encoder,
                    result.stderr[-_GPU_STDERR_TAIL:],
                )

        if self._backend.cancelled:
            return RenderOutcome.cancelled()

        cpu_args = self._codecs.cpu(preset)
        command = self._commands.build(
            request,
            preset,
            filter_complex,
            cpu_args,
            bitrate,
            gpu=False,
        )
        result = self._backend.run(command)
        if result is None:
            return RenderOutcome.cancelled()
        if result.returncode != 0:
            return RenderOutcome.failed(result.stderr[-_CPU_STDERR_TAIL:])
        return RenderOutcome.succeeded(
            size_mb=self._backend.output_size_mb(request.output_path),
            resolution=resolution,
            fps=fps.output_fps,
            encoder="libx264",
        )


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

    @override
    def execute(self, request: RenderJobRequest) -> RenderJobResult:
        """Plan the segments, render each and return the aggregate result."""
        segments = self._planner.plan(request.spec.trim, request.max_duration)
        if len(segments) == 1:
            outcome = self._render.execute(request.spec)
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
                self._render.execute(seg_spec),
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
