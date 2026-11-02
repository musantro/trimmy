"""Observable playback lifecycle and Qt delivery checks."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from tests.mothers import make_spec
from trimmy.apps.desktop.bootstrap import create_preview_playback
from trimmy.apps.desktop.main_window import (
    MainWindow,
    QueuedRenderGroup,
    QueuedRenderJob,
    RenderQueueDialog,
)
from trimmy.apps.desktop.preview_playback import PlaybackResources, PreviewPlayback
from trimmy.apps.desktop.views.render_view import RenderView
from trimmy.rendering.domain.models import RenderQueueItem, RenderTarget


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def resources():
    return PlaybackResources(
        Mock(spec=QMediaPlayer),
        Mock(spec=QAudioOutput),
        Mock(spec=QVideoSink),
    )


def callback(signal):
    return signal.connect.call_args.args[0]


def test_replacement_looping_and_teardown(app):
    first, second = resources(), resources()
    factory = Mock(side_effect=[first, second])
    playback = PreviewPlayback(factory)
    display = Mock()
    playback.start(Path("first.mp4"), 1.5, 3, display)
    first.audio.setMuted.assert_called_once_with(True)  # noqa: FBT003
    first.audio.setVolume.assert_called_once_with(0.0)
    first.player.setSource.assert_called_once_with(QUrl.fromLocalFile("first.mp4"))
    position = callback(first.player.positionChanged)
    status = callback(first.player.mediaStatusChanged)
    frame = callback(first.sink.videoFrameChanged)
    position(2000)
    first.player.setPosition.assert_not_called()
    for ms in (0, 1499, 3000, 4000):
        position(ms)
        first.player.setPosition.assert_called_with(1500)
    status(QMediaPlayer.MediaStatus.LoadedMedia)
    status(QMediaPlayer.MediaStatus.EndOfMedia)
    assert first.player.play.call_count == 2
    status(QMediaPlayer.MediaStatus.BufferingMedia)
    assert first.player.play.call_count == 2
    frame(QVideoFrame())
    assert display.call_count == 1  # only the initial clear
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    frame(QVideoFrame(image))
    delivered = display.call_args.args[0]
    assert delivered.format() == QImage.Format.Format_ARGB32
    assert delivered.pixelColor(0, 0) == QColor("red")

    playback.start(Path("second.mp4"), 4, 5, display)
    for obj in (first.player, first.audio, first.sink):
        obj.deleteLater.assert_called_once()
    first.player.stop.assert_called_once()
    for signal in (
        first.player.positionChanged,
        first.player.mediaStatusChanged,
        first.sink.videoFrameChanged,
    ):
        signal.disconnect.assert_called_once()
    assert display.call_args.args[0].isNull()
    count = display.call_count
    frame(QVideoFrame(image))  # queued old signals remain harmless
    position(0)
    status(QMediaPlayer.MediaStatus.EndOfMedia)
    assert display.call_count == count
    second.player.setPosition.assert_not_called()
    second.player.play.assert_not_called()
    assert first.player.play.call_count == 2

    new_frame = callback(second.sink.videoFrameChanged)
    playback.stop()
    playback.stop()
    new_frame(QVideoFrame(image))
    assert display.call_args.args[0].isNull()
    second.player.stop.assert_called_once()
    for obj in (second.player, second.audio, second.sink):
        obj.deleteLater.assert_called_once()


def test_empty_trim_clears_without_creating_player(app):
    factory, display = Mock(), Mock()
    playback = PreviewPlayback(factory)
    playback.start(Path("input.mp4"), 2, 2, display)
    factory.assert_not_called()
    assert display.call_args.args[0].isNull()
    playback.stop()


def test_render_view_close_requests_cleanup(app):
    view = RenderView()
    stop = Mock()
    view.preview_stop_requested.connect(stop)
    view.close()
    stop.assert_called_once()
    view.deleteLater()


def test_qt_delivers_frames_after_replacement_and_releases_resources(app, tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "Qt playback integration requires ffmpeg on PATH"
    source = tmp_path / "preview.mp4"
    subprocess.run(  # noqa: S603 - installed ffmpeg with fixed test arguments
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x64:r=10",
            "-t",
            "1",
            "-c:v",
            "mpeg4",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    created = []

    def create():
        bundle = PlaybackResources(QMediaPlayer(), QAudioOutput(), QVideoSink())
        created.append(bundle)
        return bundle

    playback = PreviewPlayback(create)
    frames = []
    try:
        playback.start(source, 0, 0.5, frames.append)
        wait_until(app, lambda: any(not f.isNull() for f in frames))
        assert created[-1].audio.isMuted()
        playback.start(source, 0.2, 0.7, frames.append)
        assert frames[-1].isNull()
        frames.clear()
        wait_until(app, lambda: any(not f.isNull() for f in frames))
        assert frames[-1].size().width() == 64
        assert frames[-1].format() == QImage.Format.Format_ARGB32
        playback.stop()
        assert frames[-1].isNull()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert all(
            not isValid(obj)
            for bundle in created
            for obj in (bundle.player, bundle.audio, bundle.sink)
        )
    finally:
        playback.stop()


def wait_until(app, condition):
    deadline = time.monotonic() + 10
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition(), "Qt did not deliver a video frame within 10 seconds"


def test_bootstrap_selects_shared_playback():
    assert isinstance(create_preview_playback(), PreviewPlayback)


def make_job():
    spec = make_spec()
    return QueuedRenderJob(
        RenderQueueItem(RenderTarget("instagram", "reels", "max"), spec, None),
        "input.mp4",
        spec.output_path,
        1,
        3,
        0.6,
    )


def test_queue_selection_replaces_playback_and_done_stops(app):
    playback = Mock(spec=PreviewPlayback)
    group = QueuedRenderGroup((make_job(),))
    dialog = RenderQueueDialog((group, group), playback)
    assert playback.start.call_count == 1
    dialog._list.setCurrentRow(1)
    assert playback.start.call_count == 2
    source, start, end, display = playback.start.call_args.args
    assert (source, start, end) == (group.first.item.spec.source_path, 1, 3)
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    display(image)
    assert dialog._preview.frame == image
    assert dialog._preview.selection == group.first.item.spec.crops
    assert dialog._preview.split_ratio == 0.6
    dialog.reject()
    playback.stop.assert_called_once()
    dialog.close()
    assert playback.stop.call_count >= 2
    dialog.deleteLater()


def test_render_current_edit_and_job_use_shared_playback(app):
    window = Mock(spec=MainWindow)
    window._source_path = Path("current.mp4")
    window._render_playback = Mock(spec=PreviewPlayback)
    window._render_view = RenderView()
    window._editor_view = Mock()
    window._editor_view.timeline.trim_start = 0.5
    window._editor_view.timeline.trim_end = 2
    window._editor_view.crop_widget.selection = make_spec().crops
    window.split_ratio = 0.4
    MainWindow._start_render_preview(window)
    args = window._render_playback.start.call_args.args
    assert args[:3] == (Path("current.mp4"), 0.5, 2)
    assert window._render_view.preview.split_ratio == 0.4
    MainWindow._start_render_preview_for_job(window, make_job())
    args = window._render_playback.start.call_args.args
    assert args[:3] == (Path("input.mp4"), 1, 3)
    assert window._render_view.preview.split_ratio == 0.6
    assert window._render_view.preview.selection == make_job().item.spec.crops
    MainWindow._stop_render_preview(window)
    window._render_playback.stop.assert_called_once()
    window._render_view.close()
    window._render_view.deleteLater()
