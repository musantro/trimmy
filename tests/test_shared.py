"""Tests for the shared Specification, UseCase and AggregateRoot bases."""

from __future__ import annotations

from dataclasses import dataclass

from trimmy.shared.compat import override
from trimmy.shared.domain.aggregate_root import AggregateRoot
from trimmy.shared.domain.event import Event
from trimmy.shared.domain.specification import Specification
from trimmy.shared.domain.use_case import UseCase


class _GreaterThan(Specification[int]):
    def __init__(self, threshold: int) -> None:
        self._threshold = threshold

    @override
    def is_satisfied_by(self, candidate: int) -> bool:
        return candidate > self._threshold


class _IsEven(Specification[int]):
    @override
    def is_satisfied_by(self, candidate: int) -> bool:
        return candidate % 2 == 0


def test_specification_is_satisfied_by():
    assert _GreaterThan(5).is_satisfied_by(6) is True
    assert _GreaterThan(5).is_satisfied_by(4) is False


def test_specification_and():
    spec = _GreaterThan(5) & _IsEven()
    assert spec.is_satisfied_by(6) is True
    assert spec.is_satisfied_by(7) is False
    assert spec.is_satisfied_by(4) is False


def test_specification_or():
    spec = _GreaterThan(5) | _IsEven()
    assert spec.is_satisfied_by(7) is True
    assert spec.is_satisfied_by(2) is True
    assert spec.is_satisfied_by(3) is False


def test_specification_not():
    spec = ~_IsEven()
    assert spec.is_satisfied_by(3) is True
    assert spec.is_satisfied_by(4) is False


class _Doubler(UseCase[int, int]):
    def double(self, request: int) -> int:
        return request * 2


def test_use_case_exposes_domain_verb():
    assert _Doubler().double(21) == 42


@dataclass(frozen=True)
class _Renamed(Event):
    name: str


class _Catalogue(AggregateRoot):
    def rename(self, name: str) -> None:
        self.record(_Renamed(name))


def test_aggregate_root_records_and_pulls_events():
    catalogue = _Catalogue()
    assert catalogue.pull_domain_events() == []

    catalogue.rename("first")
    catalogue.rename("second")
    events = catalogue.pull_domain_events()

    assert events == [_Renamed("first"), _Renamed("second")]
    assert catalogue.pull_domain_events() == []
