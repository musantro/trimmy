"""Reusable base class for the Aggregate Root pattern."""

from __future__ import annotations

from abc import ABC

from trimmy.shared.domain.event import Event


class AggregateRoot(ABC):  # noqa: B024  # abstract marker, no abstract ops
    """
    Base for the root entity of a consistency boundary.

    An aggregate root records the domain events produced while its state
    changes; the application layer pulls those events once the operation
    completes and publishes them onto the :class:`EventBus`. Subclasses call
    :meth:`record` from their own behaviour and never touch the buffer
    directly.
    """

    def __init__(self) -> None:
        self._domain_events: list[Event] = []

    def pull_domain_events(self) -> list[Event]:
        """Return the recorded events and clear the internal buffer."""
        recorded = self._domain_events
        self._domain_events = []
        return recorded

    def record(self, event: Event) -> None:
        """Record *event* to be published after the current operation."""
        self._domain_events.append(event)
