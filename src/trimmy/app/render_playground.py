"""Deterministic playground for the render screen."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from trimmy.app.components import SidebarNavigation, TopNavBar
from trimmy.app.theme import Colors, Spacing, build_stylesheet, load_fonts
from trimmy.app.views.render_view import RenderView
from trimmy.editing.shared.domain.models import CropRect, CropSelection


@dataclass(frozen=True)
class RenderPlaygroundState:
    """A reproducible render-screen state."""

    name: str
    title: str
    global_progress: int
    estimate: str
    platform_progress: tuple[tuple[str, int], ...]
    dimmed_preview: bool = True
    done: bool = False


STATES: tuple[RenderPlaygroundState, ...] = (
    RenderPlaygroundState(
        name="queued",
        title="Queued",
        global_progress=0,
        estimate="Waiting for encoder…",
        platform_progress=(("TikTok", 0),),
    ),
    RenderPlaygroundState(
        name="starting",
        title="Starting",
        global_progress=7,
        estimate="Preparing segments…",
        platform_progress=(("TikTok", 7),),
    ),
    RenderPlaygroundState(
        name="rendering",
        title="Rendering",
        global_progress=48,
        estimate="00:38 remaining",
        platform_progress=(("TikTok", 48),),
    ),
    RenderPlaygroundState(
        name="multipart",
        title="Multipart",
        global_progress=67,
        estimate="Part 2 of 3",
        platform_progress=(
            ("TikTok part 1", 100),
            ("TikTok part 2", 67),
            ("TikTok part 3", 0),
        ),
    ),
    RenderPlaygroundState(
        name="finishing",
        title="Finishing",
        global_progress=92,
        estimate="Finalizing output…",
        platform_progress=(("TikTok", 92),),
    ),
    RenderPlaygroundState(
        name="complete",
        title="Complete",
        global_progress=100,
        estimate="Render complete!",
        platform_progress=(("TikTok", 100),),
        dimmed_preview=False,
        done=True,
    ),
)


def state_names() -> list[str]:
    """Return valid state names for CLI parsing and controls."""
    return [state.name for state in STATES]


def _make_demo_frame(width: int = 1280, height: int = 720) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(Colors.LEVEL_0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    bands = (
        QColor("#12343b"),
        QColor("#1f6f8b"),
        QColor("#99ddff"),
        QColor("#fed639"),
        QColor("#ff7a59"),
    )
    band_w = width / len(bands)
    for index, color in enumerate(bands):
        painter.fillRect(int(index * band_w), 0, int(band_w) + 1, height, color)

    painter.setPen(QColor("#ffffff"))
    for x in range(0, width, 160):
        painter.drawLine(x, 0, x, height)
    for y in range(0, height, 90):
        painter.drawLine(0, y, width, y)
    painter.end()
    return image


def _demo_selection() -> CropSelection:
    return CropSelection(
        top=CropRect(x=120, y=68, w=720, h=405),
        bottom=CropRect(x=390, y=210, w=720, h=405),
    )


class RenderPlaygroundWindow(QMainWindow):
    """Window that mounts the real render screen with fake render states."""

    def __init__(self, *, controls: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("Trimmy Render Playground")
        self.resize(1180, 820)
        self.setMinimumSize(760, 620)
        self.setStyleSheet(build_stylesheet())

        self._state_index = 0
        self._demo_frame = _make_demo_frame()

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(TopNavBar(version_text="render playground"))

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body)

        sidebar = SidebarNavigation()
        sidebar.set_active("render")
        body.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        body.addLayout(content, 1)

        if controls:
            content.addWidget(self._build_controls())

        self.render_view = RenderView()
        content.addWidget(self.render_view, 1)
        self.apply_state(STATES[self._state_index])

    def _build_controls(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"background: {Colors.SURFACE_CONTAINER};"
            f"border-bottom: 1px solid {Colors.OUTLINE_VARIANT};",
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(
            Spacing.CONTAINER_PADDING,
            Spacing.XS,
            Spacing.CONTAINER_PADDING,
            Spacing.XS,
        )
        layout.setSpacing(Spacing.SM)

        label = QLabel("Render state")
        label.setStyleSheet(f"color: {Colors.ON_SURFACE_VARIANT};")
        layout.addWidget(label)

        self._state_combo = QComboBox()
        self._state_combo.addItems(state_names())
        self._state_combo.currentIndexChanged.connect(self._on_state_changed)
        layout.addWidget(self._state_combo)

        prev_btn = QPushButton("Previous")
        prev_btn.clicked.connect(self.previous_state)
        layout.addWidget(prev_btn)

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.next_state)
        layout.addWidget(next_btn)

        layout.addStretch()
        return bar

    def _on_state_changed(self, index: int) -> None:
        self._state_index = index
        self.apply_state(STATES[index])

    def previous_state(self) -> None:
        """Move to the previous playground state."""
        self._state_index = (self._state_index - 1) % len(STATES)
        self._state_combo.setCurrentIndex(self._state_index)

    def next_state(self) -> None:
        """Move to the next playground state."""
        self._state_index = (self._state_index + 1) % len(STATES)
        self._state_combo.setCurrentIndex(self._state_index)

    def apply_state(self, state: RenderPlaygroundState) -> None:
        """Apply *state* to the real render view."""
        self.setWindowTitle(f"Trimmy Render Playground - {state.title}")
        self.render_view.reset()
        self.render_view.preview.set_frame(self._demo_frame)
        self.render_view.preview.set_selection(_demo_selection())
        self.render_view.preview.split_ratio = 0.53
        self.render_view.preview.dimmed = state.dimmed_preview
        self.render_view.set_global_progress(state.global_progress, state.estimate)
        for platform, progress in state.platform_progress:
            self.render_view.set_platform_info(platform, progress)
        if state.done:
            self.render_view.show_done()
        self.render_view.update()


def capture_states(
    out_dir: Path,
    *,
    state_filter: set[str] | None = None,
    width: int = 1180,
    height: int = 820,
) -> list[Path]:
    """Render selected playground states and save screenshots."""
    out_dir.mkdir(parents=True, exist_ok=True)
    window = RenderPlaygroundWindow(controls=False)
    window.resize(width, height)
    window.show()
    QApplication.processEvents()

    paths: list[Path] = []
    for state in STATES:
        if state_filter is not None and state.name not in state_filter:
            continue
        window.apply_state(state)
        QApplication.processEvents()
        path = out_dir / f"render-{state.name}.png"
        window.grab().save(str(path))
        paths.append(path)

    window.close()
    return paths


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        help="Save screenshots for the selected render states and exit.",
    )
    parser.add_argument(
        "--state",
        action="append",
        choices=state_names(),
        help="State to show or capture. Repeat to capture multiple states.",
    )
    parser.add_argument("--width", type=int, default=1180)
    parser.add_argument("--height", type=int, default=820)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the interactive playground or snapshot exporter."""
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.snapshot_dir is not None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = cast(QApplication, QApplication.instance() or QApplication(sys.argv))
    app.setStyle("Fusion")
    load_fonts()

    state_filter = set(args.state) if args.state else None
    if args.snapshot_dir is not None:
        paths = capture_states(
            args.snapshot_dir,
            state_filter=state_filter,
            width=args.width,
            height=args.height,
        )
        for path in paths:
            sys.stdout.write(f"{path}\n")
        return 0

    window = RenderPlaygroundWindow()
    window.resize(args.width, args.height)
    if args.state:
        selected = state_names().index(args.state[-1])
        window._state_combo.setCurrentIndex(selected)
    window.show()
    QTimer.singleShot(0, window.raise_)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
