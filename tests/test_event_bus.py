"""Tests for the in-memory event bus."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.shared.domain.event import Event
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus


@dataclass(frozen=True)
class _Ping(Event):
    value: int


@dataclass(frozen=True)
class _Pong(Event):
    pass


def test_publish_invokes_subscribed_handler():
    bus = InMemoryEventBus()
    received: list[int] = []
    bus.subscribe(_Ping, lambda event: received.append(event.value))
    bus.publish(_Ping(7))
    assert received == [7]


def test_publish_only_reaches_matching_type():
    bus = InMemoryEventBus()
    seen: list[str] = []
    bus.subscribe(_Ping, lambda _event: seen.append("ping"))
    bus.subscribe(_Pong, lambda _event: seen.append("pong"))
    bus.publish(_Pong())
    assert seen == ["pong"]


def test_multiple_handlers_run_in_subscription_order():
    bus = InMemoryEventBus()
    order: list[int] = []
    bus.subscribe(_Ping, lambda _event: order.append(1))
    bus.subscribe(_Ping, lambda _event: order.append(2))
    bus.publish(_Ping(0))
    assert order == [1, 2]


def test_publish_without_subscribers_is_a_noop():
    InMemoryEventBus().publish(_Ping(1))
