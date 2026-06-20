"""Use case that renders a single continuous clip."""

from __future__ import annotations

import logging
from collections.abc import Callable

from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.models import RenderOutcome, RenderSpec
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.rendering.domain.services import (
    BitratePlanner,
    CodecArgsFactory,
    CommandBuilder,
    DimensionPlanner,
    FilterGraphBuilder,
    FpsPlanner,
)
from trimmy.shared.domain.use_case import UseCase

logger = logging.getLogger(__name__)

_GPU_STDERR_TAIL = 500
_CPU_STDERR_TAIL = 2000


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

    def render(
        self,
        request: RenderSpec,
        *,
        on_progress: Callable[[int], None] | None = None,
    ) -> RenderOutcome:
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
        duration = request.trim.duration

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
                result = self._backend.run(
                    command,
                    duration=duration,
                    on_progress=on_progress,
                )
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
        result = self._backend.run(
            command,
            duration=duration,
            on_progress=on_progress,
        )
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
