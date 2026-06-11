"""Shared fixtures and PySide6 stubs for the test suite.

PySide6 stubs are installed into sys.modules at import time (before any
test is collected) so that trimmy modules importing Qt classes can be
loaded without a real display server or Qt installation.
"""

import sys
import types

import pytest

from tests.mothers import make_crop_rect

# ---------------------------------------------------------------------------
# PySide6 stubs — lightweight placeholder classes so that `from PySide6.X
# import Y` works and real class bodies (with staticmethod, Signal, etc.)
# can execute without a live Qt runtime.
# ---------------------------------------------------------------------------

def _make_stub(name, attrs=None):
    """Return a new module with stub classes/objects for every name in *attrs*."""
    mod = types.ModuleType(name)
    for attr_name in (attrs or []):
        # Each attribute becomes a no-op class unless overridden below.
        setattr(mod, attr_name, type(attr_name, (), {}))
    return mod


class _Signal:
    """Minimal stand-in for PySide6.QtCore.Signal."""
    def __init__(self, *args, **kwargs):
        pass
    def __set_name__(self, owner, name):
        self._name = name
    def __get__(self, obj, objtype=None):
        return self
    def connect(self, *a):
        pass
    def emit(self, *a):
        pass
    def disconnect(self, *a):
        pass


# -- PySide6 top-level --
if "PySide6" not in sys.modules:
    sys.modules["PySide6"] = _make_stub("PySide6")

# -- PySide6.QtCore --
_qt_core = _make_stub("PySide6.QtCore", [
    "Qt", "QUrl", "QRectF", "QPointF", "QSize",
])
# QThread needs __init_subclass__ so class bodies with `Signal` class-vars work.
class _QThread:
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)

_qt_core.QThread = _QThread
_qt_core.Signal = _Signal
sys.modules["PySide6.QtCore"] = _qt_core

# -- PySide6.QtGui --
_qt_gui = _make_stub("PySide6.QtGui", [
    "QImage", "QPainter", "QFont", "QColor", "QPen", "QCursor",
    "QPaintEvent", "QResizeEvent", "QKeyEvent", "QMouseEvent",
    "QDragEnterEvent", "QDragLeaveEvent", "QDropEvent", "QCloseEvent",
])
sys.modules["PySide6.QtGui"] = _qt_gui

# -- PySide6.QtWidgets --
_qt_widgets = _make_stub("PySide6.QtWidgets", [
    "QApplication", "QMainWindow", "QWidget", "QVBoxLayout", "QHBoxLayout",
    "QPushButton", "QLabel", "QFileDialog", "QMessageBox", "QFrame",
    "QSizePolicy", "QMenu",
])
sys.modules["PySide6.QtWidgets"] = _qt_widgets

# -- PySide6.QtMultimedia --
_qt_multimedia = _make_stub("PySide6.QtMultimedia", [
    "QMediaPlayer", "QVideoSink", "QAudioOutput",
])
sys.modules["PySide6.QtMultimedia"] = _qt_multimedia


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config_dir(tmp_path, monkeypatch):
    """Patch config.CONFIG_PATH to use a temporary directory."""
    cfg_path = tmp_path / "trimmy" / "config.json"
    import trimmy.config as config_mod
    monkeypatch.setattr(config_mod, "CONFIG_PATH", cfg_path)
    return cfg_path


@pytest.fixture()
def crop_rect_factory():
    """Return the make_crop_rect factory from mothers."""
    return make_crop_rect


@pytest.fixture(autouse=True)
def reset_gpu_cache():
    """Reset renderer GPU detection cache between tests."""
    import trimmy.renderer as renderer_mod
    renderer_mod._gpu_encoder_cache = None
    renderer_mod._gpu_detection_done = False
    yield
    renderer_mod._gpu_encoder_cache = None
    renderer_mod._gpu_detection_done = False
