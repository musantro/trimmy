"""Synchronous, in-process event bus for tests and headless contexts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from trimmy.shared.compat import override
from trimmy.shared.domain.event import Event
from trimmy.shared.domain.event_bus import EventBus

_E = TypeVar("_E", bound=Event)


class InMemoryEventBus(EventBus):
    """
    Dispatches each event to its handlers immediately, on the caller's thread.

    Delivery is synchronous and ordered by subscription, which makes the bus
    trivial to assert against in tests without any PySide6 dependency.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Callable[[Any], None]]] = {}

    @override
    def publish(self, event: Event) -> None:
        """Call every handler subscribed to *event*'s exact type."""
        for handler in self._handlers.get(type(event), []):
            handler(event)

    @override
    def subscribe(
        self,
        event_type: type[_E],
        handler: Callable[[_E], None],
    ) -> None:
        """Register *handler* to receive events of *event_type*."""
        self._handlers.setdefault(event_type, []).append(handler)
