"""Reusable base class for the Use Case (application service) pattern."""

from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class UseCase(ABC, Generic[TRequest, TResponse]):
    """
    A single application operation mapping a request to a response.

    Subclasses expose a domain-appropriate verb (for example ``load``,
    ``move`` or ``render``) rather than a generic ``execute`` method.
    """
