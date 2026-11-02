"""Render session transitions shared by input adapters."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
class RenderSessionState:
    """Immutable observable state of the current render."""

    status: RenderSessionStatus = "idle"
    groups: tuple[tuple[RenderQueueItem, ...], ...] = ()
    progress: tuple[int, ...] = ()
    global_progress: int = 0
    saved_queue: bool = False

    @property
    def active(self) -> bool:
        """Keep the session occupied until cancellation is acknowledged."""
        return self.status in {"running", "cancelling"}

    @property
    def items(self) -> tuple[RenderQueueItem, ...]:
        """Return targets in execution order, preserving queued cut ownership."""
        return tuple(item for group in self.groups for item in group)

    @property
    def item_group_indexes(self) -> tuple[int, ...]:
        """Map each target to the queued cut that owns it."""
        return tuple(index for index, group in enumerate(self.groups) for _ in group)

    def group_progress(self, index: int) -> int:
        """Return mean target progress for a queued cut, or zero if absent."""
        values = [
            pct
            for pct, owner in zip(self.progress, self.item_group_indexes, strict=True)
            if owner == index
        ]
        return int(sum(values) / len(values)) if values else 0


@dataclass(frozen=True)
class RenderSessionStarted(Event):
    """An initialized snapshot ready for presentation before execution."""

    state: RenderSessionState


class RenderSession:
    """Own render startup, progress, cancellation and terminal state."""

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
        return self._start((items,), saved_queue=False)

    def start_queue(self, groups: tuple[tuple[RenderQueueItem, ...], ...]) -> bool:
        """Start immutable queued cuts through the same session transitions."""
        return self._start(groups, saved_queue=True)

    def _start(
        self,
        groups: tuple[tuple[RenderQueueItem, ...], ...],
        *,
        saved_queue: bool,
    ) -> bool:
        if self._state.active or not groups or any(not group for group in groups):
            return False
        items = tuple(item for group in groups for item in group)
        self._state = RenderSessionState(
            "running",
            groups,
            (0,) * len(items),
            saved_queue=saved_queue,
        )
        self._bus.publish(RenderSessionStarted(self._state))
        self._bus.publish(StartRenderQueue(items))
        return True

    def cancel(self) -> None:
        """Request cancellation once, retaining the active job until completion."""
        if self._state.status != "running":
            return
        self._replace_status("cancelling")
        self._bus.publish(StopRendering())

    def _replace_status(self, status: RenderSessionStatus) -> None:
        self._state = replace(self._state, status=status)

    def _on_progress(self, event: RenderQueueProgressed) -> None:
        state = self._state
        if not state.active or not 0 <= event.item_index < len(state.items):
            return
        progress = list(state.progress)
        progress[event.item_index] = event.target_pct
        self._state = replace(
            state,
            progress=tuple(progress),
            global_progress=event.global_pct,
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
            self._state = replace(
                self._state,
                status="completed",
                progress=(100,) * len(self._state.items),
                global_progress=100,
            )
