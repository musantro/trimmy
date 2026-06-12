"""Reusable base class for the Use Case (application service) pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class UseCase(ABC, Generic[TRequest, TResponse]):
    """A single application operation mapping a request to a response."""

    @abstractmethod
    def execute(self, request: TRequest) -> TResponse:
        """Carry out the use case for *request* and return its response."""
        ...
