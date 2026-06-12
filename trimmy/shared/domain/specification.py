"""
Reusable base classes for the Specification pattern.

A :class:`Specification` encapsulates a single predicate over a candidate
object and can be composed with other specifications using the ``&``, ``|``
and ``~`` operators, keeping business rules small, named and combinable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from trimmy.shared.compat import override

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """Abstract predicate that a candidate object may or may not satisfy."""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return whether *candidate* satisfies this specification."""
        ...

    def __and__(self, other: Specification[T]) -> Specification[T]:
        """Combine two specifications with a logical AND."""
        return _AndSpecification(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        """Combine two specifications with a logical OR."""
        return _OrSpecification(self, other)

    def __invert__(self) -> Specification[T]:
        """Negate this specification."""
        return _NotSpecification(self)


class _AndSpecification(Specification[T]):
    """Conjunction of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    @override
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return whether *candidate* satisfies both operands."""
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(
            candidate,
        )


class _OrSpecification(Specification[T]):
    """Disjunction of two specifications."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    @override
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return whether *candidate* satisfies either operand."""
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(
            candidate,
        )


class _NotSpecification(Specification[T]):
    """Negation of a specification."""

    def __init__(self, operand: Specification[T]) -> None:
        self._operand = operand

    @override
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return whether *candidate* fails the wrapped specification."""
        return not self._operand.is_satisfied_by(candidate)
