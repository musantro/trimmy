"""Render preparation through its application interface, without Qt or FFmpeg."""

from dataclasses import replace
from pathlib import Path

import pytest

from tests.mothers import make_selection
from trimmy.editing.crop.domain import CropRect, CropSelection
from trimmy.editing.trim.domain import TrimRange
from trimmy.rendering.application.prepare_render_jobs import (
    EditSnapshot,
    PrepareRenderJobs,
)
from trimmy.rendering.domain.models import RenderTarget
from trimmy.rendering.infrastructure.in_memory_preset_repository import (
    InMemoryPresetRepository,
)


def snapshot():
    return EditSnapshot(
        Path("source.mp4"), TrimRange(2, 152), make_selection(), 0.4, 59.94
    )


def test_snapshot_targets_and_reservations():
    prep = PrepareRenderJobs(
        InMemoryPresetRepository(), lambda p: p == Path("out_part1.mp4")
    )
    edit = snapshot()
    targets = (
        RenderTarget("instagram", "reels", "max"),
        RenderTarget("tiktok", "video", "lite"),
    )
    jobs = prep.prepare(
        edit, targets, (Path("out.mp4"), Path("out.mp4")), avoid_collisions=True
    )
    assert jobs[0].spec.output_path == Path("out_1.mp4")
    assert jobs[1].spec.output_path == Path("out.mp4")
    assert jobs[0].target == targets[0]
    assert jobs[1].target == targets[1]
    assert jobs[0].spec.source_path == edit.source_path
    assert jobs[0].spec.trim == TrimRange(2, 152)
    assert jobs[0].spec.crops == edit.crops
    assert jobs[0].spec.split_ratio == 0.4
    assert jobs[0].spec.source_fps == 59.94
    assert jobs[1].spec.quality == "lite"
    assert Path("out_1_part1.mp4") in prep.output_paths(jobs[0])
    edit = replace(
        edit,
        trim=TrimRange(0, 5),
        crops=CropSelection(CropRect(), CropRect()),
        split_ratio=0.7,
    )
    assert jobs[0].spec.trim == TrimRange(2, 152)
    assert jobs[0].spec.crops == make_selection()
    assert jobs[0].spec.split_ratio == 0.4


def test_single_cli_overwrites_and_gui_avoids_reservations():
    prep = PrepareRenderJobs(InMemoryPresetRepository(), lambda _p: False)
    target = RenderTarget("instagram", "reels", "max")
    edit = replace(snapshot(), trim=TrimRange(0, 5))
    path = Path("chosen.mov")
    reserved = frozenset({path})
    cli = prep.prepare(edit, (target,), (path,), reserved=reserved)
    assert cli[0].spec.output_path == path
    assert prep.output_paths(cli[0]) == (path,)
    gui = prep.prepare(
        edit, (target,), (path,), reserved=reserved, avoid_collisions=True
    )
    assert gui[0].spec.output_path == Path("chosen_1.mov")
    assert prep.prepare(edit, (), ()) == ()
    with pytest.raises(ValueError):
        prep.prepare(edit, (target,), ())


def test_names_and_full_duplicate_intent():
    prep = PrepareRenderJobs(InMemoryPresetRepository(), lambda _p: True)
    target = RenderTarget("instagram", "reels", "max")
    assert (
        prep.output_name(Path("source.mov"), target, None)
        == "source_instagram_reels_max.mp4"
    )
    assert (
        prep.output_name(Path("source.mov"), target, 2)
        == "source_2_instagram_reels_max.mp4"
    )
    edit = snapshot()
    jobs = prep.prepare(edit, (target,), (Path("out.mp4"),))
    assert prep.same_jobs(jobs, prep.prepare(edit, (target,), (Path("out.mp4"),)))
    for changed in (
        replace(edit, crops=CropSelection(CropRect(), CropRect())),
        replace(edit, split_ratio=0.8),
        replace(edit, trim=TrimRange(0, 10)),
    ):
        assert not prep.same_jobs(
            jobs, prep.prepare(changed, (target,), (Path("out.mp4"),))
        )
    assert not prep.same_jobs(
        jobs, prep.prepare(edit, (replace(target, quality="lite"),), (Path("out.mp4"),))
    )
    assert not prep.same_jobs(jobs, prep.prepare(edit, (target,), (Path("other.mp4"),)))


def test_batch_reserves_each_prepared_output():
    prep = PrepareRenderJobs(InMemoryPresetRepository(), lambda _p: False)
    target = RenderTarget("instagram", "reels", "max")
    jobs = prep.prepare(
        snapshot(),
        (target, target),
        (Path("out.mp4"), Path("out.mp4")),
        avoid_collisions=True,
    )
    assert jobs[0].spec.output_path == Path("out.mp4")
    assert jobs[1].spec.output_path == Path("out_1.mp4")
