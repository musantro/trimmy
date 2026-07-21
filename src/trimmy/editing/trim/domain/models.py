"""Trim value objects for the editing trim module."""

from __future__ import annotations

from dataclasses import dataclass

MIN_TRIM_GAP = 0.1


@dataclass(frozen=True)
class TrimRange:
    """A start/end time window selected from the source timeline."""

    start: float
    end: float

    @property
    def duration(self) -> float:
        """Return the length of the trim window in seconds."""
        return self.end - self.start

    @classmethod
    def full(cls, total: float) -> TrimRange:
        """Return a range spanning the whole ``[0, total]`` timeline."""
        return cls(0.0, total)

    def with_start(self, value: float) -> TrimRange:
        """Return a copy with the start moved to *value*, kept valid."""
        start = max(0.0, min(value, self.end - MIN_TRIM_GAP))
        return TrimRange(start, self.end)

    def with_end(self, value: float, total: float) -> TrimRange:
        """Return a copy with the end moved to *value*, kept valid."""
        end = min(total, max(value, self.start + MIN_TRIM_GAP))
        return TrimRange(self.start, end)
