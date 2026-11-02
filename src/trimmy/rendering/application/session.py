"""Direct-render session transitions shared by input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trimmy.rendering.domain.messages import (
    RenderQueueCompleted,
    RenderQueueProgressed,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import RenderQueueItem
from trimmy.shared.domain.event import Event
from trimmy.shared.domain.event_bus import EventBus

RenderSessionStatus = Literal[
    "idle", "running", "cancelling", "cancelled", "failed", "completed"
]


@dataclass(frozen=True)
class DirectRenderStarted(Event):
    """A session is initialized and ready for presentation before execution."""

    items: tuple[RenderQueueItem, ...]


@dataclass(frozen=True)
class RenderSessionState:
    """Immutable observable state of the current direct render."""

    status: RenderSessionStatus = "idle"
    items: tuple[RenderQueueItem, ...] = ()
    progress: tuple[int, ...] = ()
    global_progress: int = 0

    @property
    def active(self) -> bool:
        """Keep the session occupied until cancellation is acknowledged."""
        return self.status in {"running", "cancelling"}


class RenderSession:
    """Own direct-render startup, progress, cancellation and terminal state."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._state = RenderSessionState()
        bus.subscribe(RenderQueueProgressed, self._on_progress)
        bus.subscribe(RenderQueueCompleted, self._on_completed)

    @property
    def state(self) -> RenderSessionState:
        """Return a snapshot without exposing mutable business state."""
        return self._state

    def start(self, items: tuple[RenderQueueItem, ...]) -> bool:
        """Reserve a session before notifying presentation and execution."""
        if self._state.active or not items:
            return False
        self._state = RenderSessionState("running", items, (0,) * len(items))
        self._bus.publish(DirectRenderStarted(items))
        self._bus.publish(StartRenderQueue(items))
        return True

    def cancel(self) -> None:
        """Request cancellation once, retaining the active job until completion."""
        if self._state.status != "running":
            return
        self._replace_status("cancelling")
        self._bus.publish(StopRendering())

    def _replace_status(self, status: RenderSessionStatus) -> None:
        state = self._state
        self._state = RenderSessionState(
            status,
            state.items,
            state.progress,
            state.global_progress,
        )

    def _on_progress(self, event: RenderQueueProgressed) -> None:
        state = self._state
        if not state.active or not 0 <= event.item_index < len(state.items):
            return
        progress = list(state.progress)
        progress[event.item_index] = event.target_pct
        self._state = RenderSessionState(
            state.status,
            state.items,
            tuple(progress),
            event.global_pct,
        )

    def _on_completed(self, event: RenderQueueCompleted) -> None:
        if not self._state.active:
            return
        result = event.result
        if result.is_cancelled or (
            self._state.status == "cancelling"
            and len(result.entries) < len(self._state.items)
        ):
            self._replace_status("cancelled")
        elif result.failures:
            self._replace_status("failed")
        else:
            self._state = RenderSessionState(
                "completed",
                self._state.items,
                (100,) * len(self._state.items),
                100,
            )
