"""Use case that probes the metadata of a source file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trimmy.rendering.domain.gateways import VideoProber
from trimmy.rendering.domain.models import VideoMetadata
from trimmy.shared.domain.use_case import UseCase


@dataclass(frozen=True)
class ProbeVideoRequest:
    """Request to probe the metadata of a source file."""

    path: Path


class ProbeVideoUseCase(UseCase[ProbeVideoRequest, VideoMetadata]):
    """Reads metadata from a source video via the prober gateway."""

    def __init__(self, prober: VideoProber) -> None:
        self._prober = prober

    def probe(self, request: ProbeVideoRequest) -> VideoMetadata:
        """Return the probed metadata for the requested path."""
        return self._prober.probe(request.path)
