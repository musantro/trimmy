"""
PySide6 event bus that marshals delivery onto its owner thread.

The bus is a :class:`QObject`; publishing emits an internal signal that Qt
delivers (queued when crossing threads) to a slot on the thread that owns the
bus. Subscribers therefore always run on the owner thread — typically the GUI
thread — so handlers may touch widgets safely even when an event is published
from a worker thread.
"""

from __future__ import annotations

from abc import ABCMeta
from collections.abc import Callable
from typing import Any, TypeVar

from PySide6.QtCore import QObject, Signal, Slot

from trimmy.shared.compat import override
from trimmy.shared.domain.event import Event
from trimmy.shared.domain.event_bus import EventBus

_E = TypeVar("_E", bound=Event)


# Qt's real (Shiboken) metaclass is a subclass of ``type``, so uniting it with
# ABCMeta resolves cleanly at runtime; ty only sees the ``type`` stub, hence the
# suppressions below.
class _QObjectABCMeta(type(QObject), ABCMeta):  # ty: ignore[inconsistent-mro]
    """Metaclass uniting Qt's metaclass with ABCMeta to allow the mix-in."""


class PySideEventBus(QObject, EventBus, metaclass=_QObjectABCMeta):  # ty: ignore[conflicting-metaclass]
    """An :class:`EventBus` whose delivery is marshalled by Qt's event loop."""

    _emitted = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handlers: dict[type[Event], list[Callable[[Any], None]]] = {}
        self._emitted.connect(self._dispatch)

    @override
    def publish(self, event: Event) -> None:
        """Queue *event* for delivery on the bus owner's thread."""
        self._emitted.emit(event)

    @override
    def subscribe(
        self,
        event_type: type[_E],
        handler: Callable[[_E], None],
    ) -> None:
        """Register *handler* to receive events of *event_type*."""
        self._handlers.setdefault(event_type, []).append(handler)

    @Slot(object)
    def _dispatch(self, event: Event) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)
