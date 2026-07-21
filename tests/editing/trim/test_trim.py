"""Tests for the trim domain and application layers."""

from __future__ import annotations

from trimmy.editing.trim.application.set_trim_end_use_case import (
    SetTrimEndRequest,
    SetTrimEndUseCase,
)
from trimmy.editing.trim.application.set_trim_start_at_playhead_use_case import (
    SetTrimStartAtPlayheadRequest,
    SetTrimStartAtPlayheadUseCase,
)
from trimmy.editing.trim.application.set_trim_start_use_case import (
    SetTrimStartRequest,
    SetTrimStartUseCase,
)
from trimmy.editing.trim.domain.models import TrimRange
from trimmy.editing.trim.domain.specifications import ValidTrimRangeSpecification
from trimmy.rendering.application.plan_segments_use_case import (
    PlanSegmentsRequest,
    PlanSegmentsUseCase,
)
from trimmy.rendering.domain.models import Segment
from trimmy.rendering.domain.services import SegmentPlanner
from trimmy.rendering.domain.specifications import ExceedsMaxDurationSpecification

# ---- models ----


def test_trim_range_duration_and_full():
    assert TrimRange(2.0, 5.0).duration == 3.0
    full = TrimRange.full(60.0)
    assert full.start == 0.0
    assert full.end == 60.0


def test_trim_range_with_start_clamps():
    base = TrimRange(0.0, 10.0)
    assert base.with_start(4.0).start == 4.0
    assert base.with_start(-5.0).start == 0.0
    assert base.with_start(20.0).start == 9.9


def test_trim_range_with_end_clamps():
    base = TrimRange(2.0, 10.0)
    assert base.with_end(8.0, 20.0).end == 8.0
    assert base.with_end(50.0, 20.0).end == 20.0
    assert base.with_end(0.0, 20.0).end == 2.1


def test_segment_properties():
    seg = Segment(index=1, total=1, start=0.0, end=5.0)
    assert seg.duration == 5.0
    assert seg.is_only is True
    assert Segment(1, 3, 0.0, 5.0).is_only is False


# ---- specifications ----


def test_valid_trim_range_specification():
    spec = ValidTrimRangeSpecification()
    assert spec.is_satisfied_by(TrimRange(0.0, 5.0)) is True
    assert spec.is_satisfied_by(TrimRange(5.0, 5.0)) is False
    assert spec.is_satisfied_by(TrimRange(-1.0, 5.0)) is False


def test_exceeds_max_duration_specification():
    spec = ExceedsMaxDurationSpecification(10.0)
    assert spec.is_satisfied_by(TrimRange(0.0, 15.0)) is True
    assert spec.is_satisfied_by(TrimRange(0.0, 5.0)) is False


# ---- segment planner ----


def test_planner_single_segment_when_no_max():
    segments = SegmentPlanner().plan(TrimRange(0.0, 100.0), None)
    assert segments == [Segment(1, 1, 0.0, 100.0)]


def test_planner_single_segment_when_within_max():
    segments = SegmentPlanner().plan(TrimRange(0.0, 50.0), 60.0)
    assert len(segments) == 1
    assert segments[0].is_only is True


def test_planner_splits_into_equal_parts():
    segments = SegmentPlanner().plan(TrimRange(0.0, 25.0), 10.0)
    assert len(segments) == 3
    part = 25.0 / 3
    assert segments[0] == Segment(1, 3, 0.0, part)
    assert segments[1] == Segment(2, 3, part, 2 * part)
    assert segments[2] == Segment(3, 3, 2 * part, 25.0)


# ---- use cases ----


def test_set_trim_start_use_case():
    updated = SetTrimStartUseCase().set_start(
        SetTrimStartRequest(TrimRange(0.0, 10.0), 4.0),
    )
    assert updated.start == 4.0


def test_set_trim_start_at_playhead_moves_end_when_after_current_end():
    updated = SetTrimStartAtPlayheadUseCase().set_start(
        SetTrimStartAtPlayheadRequest(TrimRange(2.0, 10.0), 15.0, 30.0),
    )
    assert updated == TrimRange(15.0, 15.0)


def test_set_trim_start_at_playhead_keeps_end_when_inside_current_range():
    updated = SetTrimStartAtPlayheadUseCase().set_start(
        SetTrimStartAtPlayheadRequest(TrimRange(2.0, 10.0), 6.0, 30.0),
    )
    assert updated == TrimRange(6.0, 10.0)


def test_set_trim_end_use_case():
    updated = SetTrimEndUseCase().set_end(
        SetTrimEndRequest(TrimRange(0.0, 10.0), 8.0, 20.0),
    )
    assert updated.end == 8.0


def test_plan_segments_use_case():
    segments = PlanSegmentsUseCase().plan(
        PlanSegmentsRequest(TrimRange(0.0, 25.0), 10.0),
    )
    assert len(segments) == 3
