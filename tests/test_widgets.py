"""Test non-GUI logic from widgets module.

PySide6 is stubbed out by conftest.py so the module can be imported
without a display server.  We only test pure static/class methods.
"""

from trimmy.widgets import TimelineWidget


def test_timeline_fmt():
    assert TimelineWidget._fmt(65.5) == "1:05.5"


def test_timeline_fmt_zero():
    assert TimelineWidget._fmt(0) == "0:00.0"


def test_timeline_fmt_exact_minute():
    assert TimelineWidget._fmt(60.0) == "1:00.0"


def test_timeline_fmt_fractional():
    assert TimelineWidget._fmt(5.3) == "0:05.3"


def test_timeline_fmt_large():
    assert TimelineWidget._fmt(125.7) == "2:05.7"
