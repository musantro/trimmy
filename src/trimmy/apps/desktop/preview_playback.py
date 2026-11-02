"""Shared, muted trim playback for desktop previews."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl, SignalInstance
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink


@dataclass(frozen=True)
class PlaybackResources:
    """Qt objects selected by bootstrap; injectable for deterministic signal tests."""

    player: QMediaPlayer
    audio: QAudioOutput
    sink: QVideoSink


class PreviewPlayback:
    """Own source replacement, frame conversion, looping and resource release."""

    def __init__(self, create_resources: Callable[[], PlaybackResources]) -> None:
        self._create_resources = create_resources
        self._resources: PlaybackResources | None = None
        self._connections: list[tuple[SignalInstance, Callable[..., None]]] = []
        self._display: Callable[[QImage], None] | None = None

    def start(
        self,
        source: Path,
        trim_start: float,
        trim_end: float,
        display: Callable[[QImage], None],
    ) -> None:
        """Replace playback with a fresh muted source and a trim range in seconds."""
        self.stop()
        self._display = display
        display(QImage())
        if trim_end <= trim_start:
            return
        resources = self._create_resources()
        self._resources = resources
        player, audio, sink = resources.player, resources.audio, resources.sink
        audio.setMuted(True)
        audio.setVolume(0.0)
        player.setAudioOutput(audio)
        player.setVideoSink(sink)
        start_ms, end_ms = int(trim_start * 1000), int(trim_end * 1000)

        def on_frame(frame: QVideoFrame) -> None:
            if self._resources is not resources:
                return
            image = frame.toImage()
            if not image.isNull():
                display(image.convertToFormat(QImage.Format.Format_ARGB32))

        def on_position(ms: int) -> None:
            if self._resources is resources and (ms < start_ms or ms >= end_ms):
                player.setPosition(start_ms)

        def on_status(status: QMediaPlayer.MediaStatus) -> None:
            if self._resources is resources and status in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.EndOfMedia,
            ):
                player.setPosition(start_ms)
                player.play()

        self._connections = [
            (sink.videoFrameChanged, on_frame),
            (player.positionChanged, on_position),
            (player.mediaStatusChanged, on_status),
        ]
        for signal, callback in self._connections:
            signal.connect(callback)
        player.setSource(QUrl.fromLocalFile(str(source)))

    def stop(self) -> None:
        """Invalidate callbacks before stopping and releasing all Qt resources."""
        resources, self._resources = self._resources, None
        for signal, callback in self._connections:
            signal.disconnect(callback)
        self._connections.clear()
        if resources is not None:
            resources.player.stop()
            resources.player.setSource(QUrl())
            for resource in (resources.player, resources.audio, resources.sink):
                resource.deleteLater()
        if self._display is not None:
            self._display(QImage())
            self._display = None
