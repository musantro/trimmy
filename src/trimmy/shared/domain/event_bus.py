"""Abstract publish/subscribe bus for commands and domain events."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from trimmy.shared.domain.event import Event

_E = TypeVar("_E", bound=Event)


class EventBus(ABC):
    """
    Delivers each published event to the handlers subscribed to its type.

    This is a generic port: it knows nothing about any particular message.
    Concrete adapters (an in-memory bus for tests, a PySide6 bus for the GUI)
    decide *how* and *on which thread* delivery happens.
    """

    @abstractmethod
    def publish(self, event: Event) -> None:
        """Deliver *event* to every handler subscribed to its exact type."""
        ...

    @abstractmethod
    def subscribe(
        self,
        event_type: type[_E],
        handler: Callable[[_E], None],
    ) -> None:
        """Register *handler* to receive events of *event_type*."""
        ...
