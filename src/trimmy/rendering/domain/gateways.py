"""Abstract gateways to the external encoding and probing tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from trimmy.rendering.domain.models import ProcessResult, VideoMetadata


class RenderingBackend(ABC):
    """Runs encoder commands and inspects their output, with cancellation."""

    @property
    @abstractmethod
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        ...

    @abstractmethod
    def detect_gpu_encoder(self) -> str | None:
        """Return the available hardware encoder name, or ``None``."""
        ...

    @abstractmethod
    def run(self, command: Sequence[str]) -> ProcessResult | None:
        """Run *command*, returning its result or ``None`` if cancelled."""
        ...

    @abstractmethod
    def output_size_mb(self, path: Path) -> float:
        """Return the size of the rendered file at *path* in megabytes."""
        ...


class VideoProber(ABC):
    """Reads metadata from a source video file."""

    @abstractmethod
    def probe(self, path: Path) -> VideoMetadata:
        """Return the probed metadata for the video at *path*."""
        ...
