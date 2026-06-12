"""Test non-GUI helpers from main_window.

PySide6 is stubbed out by conftest.py so the module can be imported
without a display server.  We only test static/class methods here.
"""


from trimmy.main_window import MainWindow
from trimmy.presets import PLATFORM_FORMATS

# --- MainWindow._fmt ---

def test_fmt_seconds_one_minute_five():
    assert MainWindow._fmt(65) == "1:05"


def test_fmt_seconds_zero():
    assert MainWindow._fmt(0) == "0:00"


def test_fmt_seconds_exact_minute():
    assert MainWindow._fmt(60) == "1:00"


def test_fmt_seconds_large():
    assert MainWindow._fmt(3661) == "61:01"


# --- MainWindow._fmt_max_duration ---

def test_fmt_max_duration_hours():
    assert MainWindow._fmt_max_duration(3600) == "1h"


def test_fmt_max_duration_minutes():
    assert MainWindow._fmt_max_duration(300) == "5 min"


def test_fmt_max_duration_seconds():
    assert MainWindow._fmt_max_duration(30) == "30s"


def test_fmt_max_duration_mixed_hours_minutes():
    assert MainWindow._fmt_max_duration(3660) == "1h 1m"


def test_fmt_max_duration_minutes_and_seconds():
    assert MainWindow._fmt_max_duration(90) == "1m 30s"


# --- MainWindow._get_format ---

def test_get_format_found():
    win = object.__new__(MainWindow)
    fmt = win._get_format("instagram", "reels")
    assert fmt["key"] == "reels"
    assert fmt["max_duration"] == 90


def test_get_format_fallback():
    win = object.__new__(MainWindow)
    fmt = win._get_format("instagram", "nonexistent_key")
    assert fmt["key"] == PLATFORM_FORMATS["instagram"][0]["key"]


def test_get_format_tiktok():
    win = object.__new__(MainWindow)
    fmt = win._get_format("tiktok", "video")
    assert fmt["key"] == "video"
    assert fmt["max_duration"] == 600
