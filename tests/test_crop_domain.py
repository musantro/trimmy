"""Tests for the crop domain layer."""

from __future__ import annotations

from tests.mothers import make_crop, make_source
from trimmy.crop.domain.models import (
    CropHandle,
    CropPosition,
    CropRect,
    CropSelection,
    SourceSize,
)
from trimmy.crop.domain.services import (
    AspectRatioCalculator,
    AspectRatioSynchronizer,
    CropMover,
    CropResizer,
    DefaultCropFactory,
)
from trimmy.crop.domain.specifications import (
    NonEmptyCropSpecification,
    WithinSourceBoundsSpecification,
    usable_crop_specification,
)

# ---- models ----


def test_crop_rect_defaults():
    rect = CropRect()
    assert rect.x == 0.0
    assert rect.y == 0.0
    assert rect.w == 0.0
    assert rect.h == 0.0


def test_crop_rect_edges_and_empty():
    rect = CropRect(10, 20, 30, 40)
    assert rect.right == 40
    assert rect.bottom == 60
    assert rect.is_empty is False
    assert CropRect(0, 0, 0, 10).is_empty is True
    assert CropRect(0, 0, 10, 0).is_empty is True


def test_crop_handle_orientation():
    assert CropHandle.NW.is_left is True
    assert CropHandle.SW.is_left is True
    assert CropHandle.NE.is_left is False
    assert CropHandle.NW.is_top is True
    assert CropHandle.NE.is_top is True
    assert CropHandle.SW.is_top is False


def test_crop_selection_get_and_replace():
    top = make_crop(0, 0, 10, 10)
    bottom = make_crop(0, 50, 10, 10)
    selection = CropSelection(top=top, bottom=bottom)
    assert selection.get(CropPosition.TOP) is top
    assert selection.get(CropPosition.BOTTOM) is bottom

    new_top = make_crop(1, 1, 5, 5)
    replaced = selection.replace(CropPosition.TOP, new_top)
    assert replaced.top is new_top
    assert replaced.bottom is bottom

    new_bottom = make_crop(2, 2, 5, 5)
    replaced2 = selection.replace(CropPosition.BOTTOM, new_bottom)
    assert replaced2.bottom is new_bottom
    assert replaced2.top is top


# ---- specifications ----


def test_non_empty_specification():
    spec = NonEmptyCropSpecification()
    assert spec.is_satisfied_by(make_crop(0, 0, 10, 10)) is True
    assert spec.is_satisfied_by(CropRect()) is False


def test_within_bounds_specification():
    spec = WithinSourceBoundsSpecification(SourceSize(100, 100))
    assert spec.is_satisfied_by(make_crop(0, 0, 100, 100)) is True
    assert spec.is_satisfied_by(make_crop(-1, 0, 10, 10)) is False
    assert spec.is_satisfied_by(make_crop(0, -1, 10, 10)) is False
    assert spec.is_satisfied_by(make_crop(95, 0, 10, 10)) is False
    assert spec.is_satisfied_by(make_crop(0, 95, 10, 10)) is False


def test_usable_crop_specification():
    spec = usable_crop_specification(SourceSize(100, 100))
    assert spec.is_satisfied_by(make_crop(0, 0, 50, 50)) is True
    assert spec.is_satisfied_by(CropRect()) is False
    assert spec.is_satisfied_by(make_crop(0, 0, 200, 50)) is False


# ---- services ----


def test_default_crop_factory():
    selection = DefaultCropFactory().create(SourceSize(1000, 1000))
    assert selection.top == CropRect(0.0, 0.0, 600.0, 450.0)
    assert selection.bottom == CropRect(200.0, 500.0, 600.0, 450.0)


def test_aspect_ratio_calculator():
    aspects = AspectRatioCalculator().calculate(1080, 1920, 0.5)
    assert aspects.top == 1080 / 960
    assert aspects.bottom == 1080 / 960


def test_aspect_synchronizer_fits_within_bounds():
    sync = AspectRatioSynchronizer()
    result = sync.synchronize(make_crop(0, 0, 400, 400), 2.0, make_source(1920, 1080))
    assert result.w == 400.0
    assert result.h == 200.0


def test_aspect_synchronizer_clamps_height_to_source():
    sync = AspectRatioSynchronizer()
    result = sync.synchronize(
        make_crop(0, 0, 4000, 100),
        1.0,
        make_source(1000, 500),
    )
    assert result.h == 500.0
    assert result.w == 500.0


def test_aspect_synchronizer_shifts_back_inside_bounds():
    sync = AspectRatioSynchronizer()
    result = sync.synchronize(
        make_crop(900, 900, 200, 200),
        1.0,
        make_source(1000, 1000),
    )
    assert result.x == 800.0
    assert result.y == 800.0
    assert result.right <= 1000
    assert result.bottom <= 1000


def test_crop_mover_clamps_to_source():
    mover = CropMover()
    moved = mover.move(make_crop(10, 10, 100, 100), -50, -50, make_source(500, 500))
    assert moved.x == 0.0
    assert moved.y == 0.0
    far = mover.move(make_crop(10, 10, 100, 100), 1000, 1000, make_source(500, 500))
    assert far.x == 400.0
    assert far.y == 400.0


def test_crop_resizer_from_se_handle():
    resizer = CropResizer()
    result = resizer.resize(
        make_crop(0, 0, 100, 100),
        CropHandle.SE,
        50,
        1.0,
        make_source(1000, 1000),
    )
    assert result.x == 0.0
    assert result.y == 0.0
    assert result.w == 150.0
    assert result.h == 150.0


def test_crop_resizer_from_nw_handle_keeps_min_size():
    resizer = CropResizer()
    result = resizer.resize(
        make_crop(100, 100, 100, 100),
        CropHandle.NW,
        500,
        1.0,
        make_source(1000, 1000),
    )
    assert result.w == 30.0
    assert result.h == 30.0
    assert result.right == 200.0
    assert result.bottom == 200.0


def test_crop_resizer_clamps_width_to_source():
    resizer = CropResizer()
    result = resizer.resize(
        make_crop(900, 0, 100, 100),
        CropHandle.SE,
        500,
        1.0,
        make_source(1000, 1000),
    )
    assert result.right <= 1000
    assert result.h == result.w


def test_crop_resizer_clamps_height_to_source():
    resizer = CropResizer()
    result = resizer.resize(
        make_crop(0, 900, 100, 100),
        CropHandle.NE,
        50,
        0.1,
        make_source(1000, 1000),
    )
    assert result.bottom <= 1000
    assert result.w == result.h * 0.1
