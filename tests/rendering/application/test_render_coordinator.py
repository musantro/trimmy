"""Tests for the render coordinator that wires the bus to the pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.mothers import make_spec
from trimmy.editing.trim.domain.models import TrimRange
from trimmy.rendering.application.coordinator import RenderCoordinator
from trimmy.rendering.application.render_segments_use_case import RenderSegmentsUseCase
from trimmy.rendering.domain.gateways import RenderingBackend
from trimmy.rendering.domain.messages import (
    RenderCompleted,
    RenderProgressed,
    RenderQueueCompleted,
    RenderQueueProgressed,
    RetryFailedRendering,
    StartRendering,
    StartRenderQueue,
    StopRendering,
)
from trimmy.rendering.domain.models import (
    ProcessResult,
    RenderJobResult,
    RenderOutcome,
    RenderQueueEntryResult,
    RenderQueueItem,
    RenderQueueResult,
    RenderTarget,
)
from trimmy.rendering.infrastructure.ffmpeg import FFmpegRenderingBackend
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)
from trimmy.shared.compat import override
from trimmy.shared.infrastructure.in_memory_event_bus import InMemoryEventBus


class _Backend(RenderingBackend):
    """Minimal backend returning canned encode results and recording cancels."""

    def __init__(self, results: list[ProcessResult | None]) -> None:
        self._results = list(results)
        self._cancelled = False
        self.cancel_calls = 0
        self.commands: list[list[str]] = []

    @property
    @override
    def cancelled(self) -> bool:
        return self._cancelled

    @override
    def cancel(self) -> None:
        self.cancel_calls += 1
        self._cancelled = True

    @override
    def detect_gpu_encoder(self) -> str | None:
        return None

    @override
    def run(
        self,
        command: Sequence[str],
        *,
        duration: float = 0.0,
        on_progress: object = None,
    ) -> ProcessResult | None:
        self.commands.append(list(command))
        return self._results.pop(0)

    @override
    def output_size_mb(self, path: Path) -> float:
        return 5.0


def _coordinator(bus: InMemoryEventBus, backend: _Backend) -> RenderCoordinator:
    use_case = RenderSegmentsUseCase(InMemoryPresetRepository(), backend)
    return RenderCoordinator(bus, use_case, backend)


def test_start_rendering_publishes_completed():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, "")])
    _coordinator(bus, backend)

    completed: list[RenderCompleted] = []
    bus.subscribe(RenderCompleted, completed.append)

    bus.publish(StartRendering(make_spec()))

    assert len(completed) == 1
    assert completed[0].result.first.is_success


def test_start_rendering_publishes_progress_for_each_part():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, "")] * 3)
    _coordinator(bus, backend)

    progress: list[int] = []
    bus.subscribe(RenderProgressed, lambda event: progress.append(event.pct))

    bus.publish(StartRendering(make_spec(trim=TrimRange(0.0, 25.0)), max_duration=10))

    assert progress == [0, 33, 66]


def test_stop_rendering_cancels_the_backend():
    bus = InMemoryEventBus()
    backend = _Backend([])
    _coordinator(bus, backend)

    bus.publish(StopRendering())

    assert backend.cancel_calls == 1


def test_start_render_queue_publishes_progress_and_completed():
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(0, ""), ProcessResult(0, "")])
    _coordinator(bus, backend)

    progress: list[RenderQueueProgressed] = []
    completed: list[RenderQueueCompleted] = []
    bus.subscribe(RenderQueueProgressed, progress.append)
    bus.subscribe(RenderQueueCompleted, completed.append)

    first = RenderTarget("instagram", "reels", "max")
    second = RenderTarget("twitter", "post", "max")
    bus.publish(
        StartRenderQueue(
            (
                RenderQueueItem(first, make_spec(platform="instagram"), None),
                RenderQueueItem(second, make_spec(platform="twitter"), None),
            ),
        ),
    )

    assert [event.target for event in progress if event.target_pct == 0] == [
        first,
        second,
    ]
    assert [event.item_index for event in progress if event.target_pct == 0] == [0, 1]
    assert progress[-1].global_pct == 100
    assert len(completed) == 1
    assert completed[0].result.parts == 2


def _run_queue(results, items):
    bus = InMemoryEventBus()
    backend = _Backend(results)
    _coordinator(bus, backend)
    completed: list[RenderQueueCompleted] = []
    bus.subscribe(RenderQueueCompleted, completed.append)
    bus.publish(StartRenderQueue(items))
    return completed[-1].result, backend


def _items():
    spec = make_spec(trim=TrimRange(10, 72), output_path=Path("cut1.mp4"))
    target = RenderTarget("instagram", "reels", "max")
    return (
        RenderQueueItem(target, spec, 60),
        RenderQueueItem(
            replace(target, platform="twitter"),
            replace(
                spec,
                platform="twitter",
                output_path=Path("cut1-twitter.mp4"),
            ),
            None,
        ),
        RenderQueueItem(
            target, replace(spec, split_ratio=0.6, output_path=Path("cut2.mp4")), None
        ),
    )


@pytest.mark.parametrize("codes", [[1, 0, 1, 0], [1, 1, 1, 1], [0, 1, 0, 1]])
def test_queue_attempts_all_segments_targets_and_cuts(codes):
    result, backend = _run_queue(
        [ProcessResult(c, f"error {i}") for i, c in enumerate(codes)], _items()
    )
    assert len(backend.commands) == 4
    outcomes = [o for entry in result.entries for o in entry.result.outcomes]
    assert [o.is_failed for o in outcomes] == [c != 0 for c in codes]
    assert [o.path for o in outcomes] == [
        "cut1_part1.mp4",
        "cut1_part2.mp4",
        "cut1-twitter.mp4",
        "cut2.mp4",
    ]
    assert [o.spec.trim for o in outcomes[:2]] == [TrimRange(10, 41), TrimRange(41, 72)]
    assert outcomes[0].error == ("error 0" if codes[0] else None)
    assert result.entries[2].item.spec.split_ratio == 0.6


def test_retry_only_failures_with_original_settings_and_retained_successes():
    original, _ = _run_queue(
        [
            ProcessResult(0, ""),
            ProcessResult(1, "bad"),
            ProcessResult(1, "bad target"),
            ProcessResult(0, ""),
        ],
        _items(),
    )
    bus = InMemoryEventBus()
    backend = _Backend([ProcessResult(1, "still bad"), ProcessResult(0, "")])
    _coordinator(bus, backend)
    reports: list[RenderQueueCompleted] = []
    bus.subscribe(RenderQueueCompleted, reports.append)
    # The current editor can change independently; retry has only the saved report.
    changed_editor = replace(_items()[0].spec, split_ratio=0.8, trim=TrimRange(0, 1))
    bus.publish(RetryFailedRendering(original))
    result = reports[-1].result
    assert [c[-1] for c in backend.commands] == ["cut1_part2.mp4", "cut1-twitter.mp4"]
    assert result.entries[0].result.first is original.entries[0].result.first
    failed = result.entries[0].result.failures[0]
    assert failed.error == "still bad"
    assert failed.spec == original.entries[0].result.outcomes[1].spec
    assert failed.spec is not None
    assert failed.spec.split_ratio != changed_editor.split_ratio
    assert len(result.failures) == 1
    assert result.entries[1].result.first.is_success


def test_cancellation_reports_active_and_all_unattempted_work():
    result, backend = _run_queue([ProcessResult(0, ""), None], _items())
    assert len(backend.commands) == 2
    assert result.is_cancelled
    assert result.entries[0].result.first.is_success
    assert result.entries[0].result.outcomes[1].is_cancelled
    assert result.entries[1].result.first.unattempted
    assert result.entries[2].result.first.unattempted
    assert not result.failures


def test_cancelling_retry_preserves_success_and_remaining_failures():
    original, _ = _run_queue(
        [
            ProcessResult(0, ""),
            ProcessResult(1, "bad"),
            ProcessResult(1, "bad target"),
            ProcessResult(1, "bad cut"),
        ],
        _items(),
    )
    bus = InMemoryEventBus()
    backend = _Backend([None])
    _coordinator(bus, backend)
    reports: list[RenderQueueCompleted] = []
    bus.subscribe(RenderQueueCompleted, reports.append)
    bus.publish(RetryFailedRendering(original))
    result = reports[-1].result
    assert len(backend.commands) == 1
    assert result.is_cancelled
    assert result.entries[0].result.first is original.entries[0].result.first
    assert result.entries[0].result.outcomes[1].is_cancelled
    assert len(result.failures) == 2


def test_single_job_retry_preserves_segment_paths():
    bus = InMemoryEventBus()
    backend = _Backend(
        [ProcessResult(1, "bad"), ProcessResult(0, ""), ProcessResult(0, "")]
    )
    _coordinator(bus, backend)
    reports: list[RenderCompleted] = []
    bus.subscribe(RenderCompleted, reports.append)
    bus.publish(StartRendering(make_spec(trim=TrimRange(0, 62)), 60))
    original = reports[-1].result
    bus.publish(RetryFailedRendering(original))
    result = reports[-1].result
    assert result.outcomes[1] is original.outcomes[1]
    assert result.first.path == original.first.path
    assert result.first.spec == original.first.spec
    assert not result.failures


def test_retry_ignores_legacy_reports_without_saved_settings():
    bus = InMemoryEventBus()
    backend = _Backend([])
    _coordinator(bus, backend)
    job = RenderJobResult((RenderOutcome.failed("old"),), multipart=False)
    bus.publish(RetryFailedRendering(job))
    bus.publish(
        RetryFailedRendering(
            RenderQueueResult(
                (
                    RenderQueueEntryResult(
                        RenderTarget("instagram", "reels", "max"), job
                    ),
                )
            )
        )
    )
    assert not backend.commands


@pytest.mark.parametrize(
    "limit,cancel_at,gpu,fail_first",
    [
        (None, 1, None, False),
        (60, 2, None, False),
        (60, 2, "h264_nvenc", False),
        (None, 2, "h264_nvenc", True),
    ],
)
def test_cancel_deletes_only_attempt_file_and_preserves_completed_files(
    tmp_path,
    limit,
    cancel_at,
    gpu,
    fail_first,
):
    backend = FFmpegRenderingBackend()
    bus = InMemoryEventBus()
    RenderCoordinator(
        bus, RenderSegmentsUseCase(InMemoryPresetRepository(), backend), backend
    )
    reports: list[RenderCompleted] = []
    bus.subscribe(RenderCompleted, reports.append)
    launches = []
    unrelated = tmp_path / "unrelated.mp4"
    unrelated.write_bytes(b"keep")

    class Process:
        returncode = 0
        stdout = StringIO()
        stderr = StringIO()

        def wait(self):
            self.communicate()

        def communicate(self):
            Path(launches[-1][-1]).write_bytes(
                b"complete" if len(launches) < cancel_at else b"partial"
            )
            if fail_first and len(launches) == 1:
                self.returncode = 1
            if len(launches) == cancel_at:
                self.returncode = -9
                bus.publish(StopRendering())
            return "", ""

        def kill(self):
            pass

    def launch(command, **kwargs):
        launches.append(command)
        return Process()

    with (
        patch.object(backend, "detect_gpu_encoder", return_value=gpu),
        patch(
            "trimmy.rendering.infrastructure.ffmpeg.subprocess.Popen",
            side_effect=launch,
        ),
    ):
        bus.publish(
            StartRendering(
                make_spec(trim=TrimRange(0, 62), output_path=tmp_path / "cut.mp4"),
                limit,
            )
        )
    result = reports[-1].result
    assert result.is_cancelled
    assert len(launches) == cancel_at
    assert unrelated.read_bytes() == b"keep"
    assert not list(tmp_path.glob("*.partial.mp4"))
    if limit is not None:
        assert (tmp_path / "cut_part1.mp4").read_bytes() == b"complete"
        assert not (tmp_path / "cut_part2.mp4").exists()
    else:
        assert not (tmp_path / "cut.mp4").exists()


def test_successful_gpu_fallback_is_not_retryable():
    from tests.rendering.application.test_render_application import FakeBackend

    backend = FakeBackend(
        gpu_encoder="h264_nvenc",
        results=[
            ProcessResult(1, "GPU unavailable"),
            ProcessResult(0, ""),
        ],
    )
    bus = InMemoryEventBus()
    RenderCoordinator(
        bus, RenderSegmentsUseCase(InMemoryPresetRepository(), backend), backend
    )
    reports: list[RenderCompleted] = []
    bus.subscribe(RenderCompleted, reports.append)
    bus.publish(StartRendering(make_spec()))
    assert not reports[-1].result.failures
    bus.publish(RetryFailedRendering(reports[-1].result))
    assert len(backend.commands) == 2


def test_report_distinguishes_outcomes_with_cut_target_and_segment_identity():
    from trimmy.apps.desktop.render_report import render_report

    result, _ = _run_queue([ProcessResult(1, "bad segment"), None], _items())
    text = render_report(result)
    assert "Cut 1:" in text
    assert "instagram_reels_max" in text
    assert "segment 1/2" in text
    assert "bad segment" in text
    assert "Failed" in text
    assert "Cancelled" in text
    assert "Unattempted" in text
    assert "cut1_part1.mp4" in text
    assert "Cut 2:" in text

    success, _ = _run_queue([ProcessResult(0, "")] * 4, _items())
    assert render_report(success).count("Succeeded") == 4
