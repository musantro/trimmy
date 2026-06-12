"""Compatibility helpers shared across the codebase."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 12):  # pragma: no cover
    from typing import override
else:  # pragma: no cover
    from typing_extensions import override

__all__ = ["override"]
