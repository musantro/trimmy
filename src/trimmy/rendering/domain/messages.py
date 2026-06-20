"""
The rendering context's published messaging contract.

Commands the context accepts (``StartRendering``, ``StopRendering``) and the
events it emits (``RenderProgressed``, ``RenderCompleted``) — the messages the
``app`` composition root publishes onto, and subscribes to from, the bus.
"""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.rendering.domain.models import RenderJobResult, RenderSpec
from trimmy.shared.domain.event import Event


@dataclass(frozen=True)
class StartRendering(Event):
    """Command: render *spec*, splitting it by *max_duration* if set."""

    spec: RenderSpec
    max_duration: int | None = None


@dataclass(frozen=True)
class StopRendering(Event):
    """Command: cancel the render currently in flight."""


@dataclass(frozen=True)
class RenderProgressed(Event):
    """Event: render is *pct* % complete (0–100)."""

    pct: int


@dataclass(frozen=True)
class RenderCompleted(Event):
    """Event: the render job finished with *result* (success or failure)."""

    result: RenderJobResult
