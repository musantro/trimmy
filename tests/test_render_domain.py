"""Tests for the render domain layer."""

from __future__ import annotations

from pathlib import Path

from tests.mothers import make_crop, make_preset, make_selection, make_spec
from trimmy.editing.shared.domain.models import TrimRange
from trimmy.rendering.domain.models import (
    BitratePlan,
    DimensionPlan,
    RenderJobResult,
    RenderOutcome,
    RenderQueueEntryResult,
    RenderQueueResult,
    RenderTarget,
    Resolution,
)
from trimmy.rendering.domain.services import (
    BitratePlanner,
    CodecArgsFactory,
    CommandBuilder,
    DimensionPlanner,
    FilterGraphBuilder,
    FormatSelector,
    FpsPlanner,
)
from trimmy.rendering.domain.specifications import (
    FpsCapRequiredSpecification,
    RequiresDynamicBitrateSpecification,
)
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)

# ---- models ----


def test_resolution_label():
    assert Resolution(1080, 1920).label == "1080x1920"


def test_encoder_preset_resolution():
    assert make_preset(width=720, height=1280).resolution == Resolution(720, 1280)


def test_render_outcome_states():
    ok = RenderOutcome.succeeded(
        size_mb=10.0,
        resolution="1080x1920",
        fps=30.0,
        encoder="libx264",
    )
    assert ok.is_success is True
    assert ok.is_failed is False
    assert ok.is_cancelled is False

    failed = RenderOutcome.failed("boom")
    assert failed.is_failed is True
    assert failed.is_success is False
    assert failed.is_cancelled is False

    cancelled = RenderOutcome.cancelled()
    assert cancelled.is_cancelled is True
    assert cancelled.is_failed is False
    assert cancelled.is_success is False


def test_render_job_result_aggregates():
    one = RenderOutcome.succeeded(
        size_mb=5.0,
        resolution="r",
        fps=30.0,
        encoder="libx264",
    )
    two = RenderOutcome.succeeded(
        size_mb=2.5,
        resolution="r",
        fps=30.0,
        encoder="libx264",
    )
    result = RenderJobResult(outcomes=(one, two), multipart=True)
    assert result.first is one
    assert result.parts == 2
    assert result.is_cancelled is False
    assert result.failures == ()
    assert result.total_size_mb == 7.5


def test_render_job_result_failures_and_cancel():
    failed = RenderOutcome.failed("bad")
    cancelled = RenderOutcome.cancelled()
    result = RenderJobResult(outcomes=(failed, cancelled), multipart=True)
    assert result.is_cancelled is True
    assert result.failures == (failed,)


def test_render_target_key():
    target = RenderTarget("instagram", "reels", "max")
    assert target.key == "instagram_reels_max"


def test_render_queue_result_aggregates():
    target = RenderTarget("instagram", "reels", "max")
    result = RenderJobResult(outcomes=(RenderOutcome.cancelled(),), multipart=False)
    entry = RenderQueueEntryResult(target, result)
    queue = RenderQueueResult(entries=(entry,))
    assert queue.entries == (entry,)
    assert queue.parts == 1
    assert queue.is_cancelled is True
    assert queue.failures == ()


# ---- specifications ----


def test_fps_cap_specification():
    spec = FpsCapRequiredSpecification(60)
    assert spec.is_satisfied_by(120.0) is True
    assert spec.is_satisfied_by(30.0) is False


def test_requires_dynamic_bitrate_specification():
    spec = RequiresDynamicBitrateSpecification()
    assert spec.is_satisfied_by(make_preset(maxrate=None)) is True
    assert spec.is_satisfied_by(make_preset(maxrate="8000k")) is False


# ---- dimension planner ----


def test_dimension_planner_rounds_even_no_adjustment():
    plan = DimensionPlanner().plan(
        make_selection(make_crop(0, 0, 501, 401), make_crop(10, 20, 503, 403)),
        0.5,
        make_preset(width=1080, height=1920),
    )
    assert plan.top_w == 500
    assert plan.top_h == 400
    assert plan.bottom_w == 502
    assert plan.bottom_h == 402
    assert plan.top_out_h == 960
    assert plan.bottom_out_h == 960


def test_dimension_planner_corrects_remainder():
    plan = DimensionPlanner().plan(
        make_selection(),
        0.505,
        make_preset(width=108, height=200),
    )
    assert plan.top_out_h + plan.bottom_out_h == 200


# ---- fps planner ----


def test_fps_planner_caps_high_fps():
    plan = FpsPlanner().plan(120.0, make_preset(max_fps=60))
    assert plan.filter_suffix == ",fps=60"
    assert plan.output_fps == 60.0


def test_fps_planner_keeps_low_fps():
    plan = FpsPlanner().plan(24.0, make_preset(max_fps=60))
    assert plan.filter_suffix == ""
    assert plan.output_fps == 24.0


# ---- filter graph ----


def test_filter_graph_builder():
    plan = DimensionPlan(
        output_width=1080,
        top_x=0,
        top_y=0,
        top_w=500,
        top_h=400,
        top_out_h=960,
        bottom_x=10,
        bottom_y=20,
        bottom_w=502,
        bottom_h=402,
        bottom_out_h=960,
    )
    graph = FilterGraphBuilder().build(plan, ",fps=60")
    assert "crop=500:400:0:0" in graph
    assert "scale=1080:960,fps=60[top]" in graph
    assert "vstack=inputs=2[out]" in graph


# ---- bitrate planner ----


def test_bitrate_planner_uses_static_values():
    plan = BitratePlanner().plan(
        make_preset(maxrate="8000k", bufsize="16000k"),
        30.0,
    )
    assert plan == BitratePlan("8000k", "16000k")


def test_bitrate_planner_computes_dynamic_values():
    plan = BitratePlanner().plan(
        make_preset(
            maxrate=None,
            bufsize=None,
            bufsize_mult=2,
            max_size_mb=16,
            audio_bitrate="128k",
        ),
        30.0,
    )
    assert plan.maxrate == "4241k"
    assert plan.bufsize == "8482k"


def test_bitrate_planner_uses_default_multiplier():
    plan = BitratePlanner().plan(
        make_preset(
            maxrate=None,
            bufsize=None,
            bufsize_mult=None,
            max_size_mb=16,
            audio_bitrate="128k",
        ),
        30.0,
    )
    assert plan.bufsize == "8482k"


# ---- codec args ----


def test_codec_args_cpu():
    args = CodecArgsFactory().cpu(make_preset(preset="slow", crf=16))
    assert args == ["-c:v", "libx264", "-preset", "slow", "-crf", "16"]


def test_codec_args_gpu_nvenc():
    args = CodecArgsFactory().gpu("h264_nvenc", make_preset(preset="slow"))
    assert args is not None
    assert "h264_nvenc" in args
    assert args[args.index("-preset") + 1] == "p6"


def test_codec_args_gpu_amf():
    args = CodecArgsFactory().gpu("h264_amf", make_preset(preset="medium"))
    assert args is not None
    assert "cqp" in args
    assert args[args.index("-quality") + 1] == "balanced"


def test_codec_args_gpu_qsv():
    args = CodecArgsFactory().gpu("h264_qsv", make_preset(preset="fast"))
    assert args is not None
    assert "-global_quality" in args
    assert args[args.index("-preset") + 1] == "fast"


def test_codec_args_gpu_unknown():
    assert CodecArgsFactory().gpu("h264_unknown", make_preset()) is None


# ---- command builder ----


def test_command_builder_cpu_level():
    cmd = CommandBuilder().build(
        make_spec(trim=TrimRange(0.0, 10.0)),
        make_preset(level="4.0"),
        "[0:v]crop=1[out]",
        ["-c:v", "libx264"],
        BitratePlan("25000k", "50000k"),
        gpu=False,
    )
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-level:v") + 1] == "4.0"
    assert str(Path("output.mp4")) in cmd


def test_command_builder_gpu_level_auto():
    cmd = CommandBuilder().build(
        make_spec(),
        make_preset(level="4.2"),
        "[0:v]crop=1[out]",
        ["-c:v", "h264_nvenc"],
        BitratePlan("25000k", "50000k"),
        gpu=True,
    )
    assert cmd[cmd.index("-level:v") + 1] == "auto"


# ---- format selector ----


def test_format_selector_finds_and_falls_back():
    formats = InMemoryPresetRepository().formats("instagram")
    selector = FormatSelector()
    assert selector.select(formats, "reels").key == "reels"
    assert selector.select(formats, "missing").key == formats[0].key
