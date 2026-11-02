"""Observable direct-render session behavior, including input intent mapping."""

from unittest.mock import MagicMock

import pytest

from tests.mothers import make_spec
from trimmy.apps.cli.domain.models import ControlError
from trimmy.apps.desktop.control_adapter import MainWindowControlAdapter
from trimmy.apps.desktop.main_window import MainWindow, QueuedRenderJob
from trimmy.rendering.application.prepare_render_jobs import PrepareRenderJobs
from trimmy.rendering.application.session import DirectRenderStarted, RenderSession
from trimmy.rendering.domain.messages import (
    RenderQueueCompleted,
    RenderQueueProgressed,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import (
    RenderJobResult,
    RenderOutcome,
    RenderQueueEntryResult,
    RenderQueueItem,
    RenderQueueResult,
    RenderTarget,
)
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus


def items():
    return (
        RenderQueueItem(RenderTarget("instagram", "reels", "max"), make_spec(), None),
    )


def result(outcome):
    return RenderQueueCompleted(
        RenderQueueResult(
            (
                RenderQueueEntryResult(
                    items()[0].target,
                    RenderJobResult((outcome,), multipart=False),
                ),
            )
        )
    )


def test_start_initializes_before_presentation_and_execution_and_rejects_duplicates():
    bus = InMemoryEventBus()
    session = RenderSession(bus)
    observed = []
    bus.subscribe(
        DirectRenderStarted, lambda event: observed.append((event, session.state))
    )
    commands = []
    bus.subscribe(StartRenderQueue, commands.append)
    assert not session.start(())
    assert session.state.status == "idle"
    assert session.start(items())
    assert observed[0][1].active
    assert observed[0][1].items == items()
    assert observed[0][1].progress == (0,)
    assert observed[0][1].global_progress == 0
    assert commands == [StartRenderQueue(items())]
    assert not session.start(items())
    assert len(commands) == 1


@pytest.mark.parametrize(
    "outcome,status",
    [
        (RenderOutcome(), "completed"),
        (RenderOutcome.failed("encoder failed"), "failed"),
        (RenderOutcome.cancelled(), "cancelled"),
    ],
)
def test_progress_completion_and_restart(outcome, status):
    bus = InMemoryEventBus()
    session = RenderSession(bus)
    session.cancel()
    bus.publish(result(outcome))
    event = RenderQueueProgressed(0, items()[0].target, 42, 42)
    bus.publish(event)
    assert session.state.status == "idle"
    session.start(items())
    snapshot = session.state
    bus.publish(RenderQueueProgressed(-1, items()[0].target, 10, 10))
    bus.publish(RenderQueueProgressed(2, items()[0].target, 10, 10))
    assert session.state == snapshot
    bus.publish(event)
    assert session.state.progress == (42,)
    assert snapshot.progress == (0,)
    bus.publish(result(outcome))
    assert session.state.status == status
    assert not session.state.active
    assert session.state.progress == ((100,) if status == "completed" else (42,))
    assert session.state.global_progress == (100 if status == "completed" else 42)
    bus.publish(event)
    assert session.state.status == status
    assert session.start(items())
    assert session.state.progress == (0,)


def test_cancel_keeps_reservation_until_acknowledged_even_before_first_target():
    bus = InMemoryEventBus()
    session = RenderSession(bus)
    stops = []
    bus.subscribe(StopRendering, stops.append)
    session.start(items())
    session.cancel()
    session.cancel()
    assert stops == [StopRendering()]
    assert session.state.active
    assert session.state.status == "cancelling"
    assert not session.start(items())
    bus.publish(RenderQueueCompleted(RenderQueueResult(())))
    assert session.state.status == "cancelled"
    assert session.start(items())


@pytest.mark.parametrize("intent", ["gui", "cli"])
def test_gui_and_cli_map_to_same_session_and_presentation(intent):
    bus = InMemoryEventBus()
    session = RenderSession(bus)
    window = MagicMock()
    window.render_session = session
    window._render_worker = None
    window.is_rendering.side_effect = lambda: MainWindow.is_rendering(window)
    window.start_direct_render.side_effect = lambda jobs: (
        MainWindow.start_direct_render(window, jobs)
    )
    window.stop_render.side_effect = lambda: MainWindow.stop_render(window)
    window._bus = bus
    item = items()[0]
    jobs = (QueuedRenderJob(item, "input.mp4", item.spec.output_path, 0, 10, 0.5),)
    window._prepare_jobs = PrepareRenderJobs(
        InMemoryPresetRepository(), lambda _: False
    )
    window._build_render_jobs.return_value = jobs
    window._source_path = item.spec.source_path
    window._choose_output_paths.return_value = {
        ("instagram", "reels"): item.spec.output_path
    }
    window._editor_view.platform_selector.selected_targets.return_value = (
        ("instagram", "reels"),
    )
    bus.subscribe(
        DirectRenderStarted,
        lambda event: MainWindow._on_direct_render_started(window, event),
    )
    commands = []
    bus.subscribe(StartRenderQueue, commands.append)
    adapter = MainWindowControlAdapter(window)
    if intent == "gui":
        MainWindow._render(window)
        MainWindow._render(window)
    else:
        adapter.render_start(item.spec.output_path, None)
        with pytest.raises(ControlError, match="already running"):
            adapter.render_start(item.spec.output_path, None)
    assert commands == [StartRenderQueue(items())]
    assert session.state.active
    assert window._render_out_path == str(item.spec.output_path)
    assert window._active_item_progress == {0: 0}
    window._render_view.reset.assert_called_once()
    window._start_render_preview.assert_called_once()
    window._switch_to_view.assert_called_once_with(2)
    assert window._editor_view.render_btn.setEnabled.call_args.args == (False,)
    adapter.render_stop()
    assert session.state.status == "cancelling"


@pytest.mark.parametrize(
    "outcome,status",
    [
        (RenderOutcome(), "completed"),
        (RenderOutcome.failed("encode failed"), "failed"),
        (RenderOutcome.cancelled(), "cancelled"),
    ],
)
def test_progress_and_terminal_presentation_follow_session(outcome, status):
    bus = InMemoryEventBus()
    session = RenderSession(bus)
    window = MagicMock()
    window.render_session = session
    window._render_worker = None
    window._render_queue = []
    window.selected_targets = (("instagram", "reels"),)
    window.is_rendering.side_effect = lambda: MainWindow.is_rendering(window)
    window._sync_queue_controls.side_effect = lambda: MainWindow._sync_queue_controls(
        window
    )
    bus.subscribe(
        DirectRenderStarted,
        lambda event: MainWindow._on_direct_render_started(window, event),
    )
    bus.subscribe(
        RenderQueueProgressed,
        lambda event: MainWindow._on_render_queue_progressed(window, event),
    )
    bus.subscribe(
        RenderQueueCompleted,
        lambda event: MainWindow._on_render_queue_completed(window, event),
    )
    session.start(items())
    bus.publish(RenderQueueProgressed(0, items()[0].target, 42, 42))
    assert window._active_item_progress == {0: 42}
    window._render_view.set_global_progress.assert_called_with(42, "--:-- remaining")
    if status == "cancelled":
        session.cancel()
    bus.publish(result(outcome))
    assert session.state.status == status
    assert not window.is_rendering()
    assert window._editor_view.stop_btn.setVisible.call_args.args == (False,)
    assert window._editor_view.render_btn.setEnabled.call_args.args == (True,)
    assert window._editor_view.send_queue_btn.setEnabled.call_args.args == (True,)
    if status == "cancelled":
        window._stop_render_preview.assert_called_once()
        window._switch_to_view.assert_called_with(1)
        assert window._active_item_progress == {}
    else:
        assert window._active_item_progress == {0: 100 if status == "completed" else 42}
        window._render_view.set_global_progress.assert_called_with(
            100 if status == "completed" else 42,
            "Render complete!" if status == "completed" else "Render failed",
        )
        window._render_view.show_done.assert_called_once()
        assert not window._render_view.preview.dimmed
