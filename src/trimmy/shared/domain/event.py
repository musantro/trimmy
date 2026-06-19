"""The base type for messages carried on the event bus."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """
    Marker base for the commands and domain events published on a bus.

    Commands (imperative, exactly one handler) and events (facts, zero or
    more handlers) share this base so a single :class:`EventBus` can carry
    both. Concrete subclasses are immutable value objects.
    """
