"""Tests for the crop application layer (use cases)."""

from __future__ import annotations

from tests.mothers import make_crop, make_selection, make_source
from trimmy.editing.crop.application.flip_output_areas_use_case import (
    FlipOutputAreasRequest,
    FlipOutputAreasUseCase,
)
from trimmy.editing.crop.application.initialize_crops_use_case import (
    InitializeCropsRequest,
    InitializeCropsUseCase,
)
from trimmy.editing.crop.application.move_crop_use_case import (
    MoveCropRequest,
    MoveCropUseCase,
)
from trimmy.editing.crop.application.resize_crop_use_case import (
    ResizeCropRequest,
    ResizeCropUseCase,
)
from trimmy.editing.crop.application.synchronize_aspects_use_case import (
    SynchronizeAspectsRequest,
    SynchronizeAspectsUseCase,
)
from trimmy.editing.crop.domain.services import CropAspects
from trimmy.editing.crop.infrastructure.in_memory_crop_selection_repository import (
    InMemoryCropSelectionRepository,
)
from trimmy.editing.shared.domain.models import CropHandle, CropPosition, CropSelection


def test_initialize_crops_use_case():
    repo = InMemoryCropSelectionRepository()
    use_case = InitializeCropsUseCase(repo)
    selection = use_case.initialize(
        InitializeCropsRequest(make_source(1000, 1000)),
    )
    assert selection.top.w == 600.0
    assert repo.get() == selection


def test_synchronize_aspects_use_case():
    repo = InMemoryCropSelectionRepository(
        make_selection(make_crop(0, 0, 400, 400), make_crop(0, 0, 400, 400)),
    )
    use_case = SynchronizeAspectsUseCase(repo)
    selection = use_case.synchronize(
        SynchronizeAspectsRequest(CropAspects(2.0, 1.0), make_source(1920, 1080)),
    )
    assert selection.top.h == 200.0
    assert selection.bottom.h == 400.0
    assert repo.get() == selection


def test_flip_output_areas_use_case_swaps_top_and_bottom_properties():
    top = make_crop(10, 20, 500, 400)
    bottom = make_crop(30, 40, 600, 500)
    repo = InMemoryCropSelectionRepository(make_selection(top, bottom))
    result = FlipOutputAreasUseCase(repo).flip(FlipOutputAreasRequest(0.6))

    assert result.selection.top == bottom
    assert result.selection.bottom == top
    assert result.split_ratio == 0.4
    assert repo.get() == result.selection


def test_move_crop_use_case():
    repo = InMemoryCropSelectionRepository(make_selection())
    use_case = MoveCropUseCase(repo)
    selection = use_case.move(
        MoveCropRequest(
            CropPosition.TOP,
            make_crop(0, 0, 100, 100),
            -50,
            -50,
            make_source(500, 500),
        ),
    )
    assert selection.top.x == 0.0
    assert selection.top.y == 0.0
    assert repo.get() == selection


def test_resize_crop_use_case():
    repo = InMemoryCropSelectionRepository(make_selection())
    use_case = ResizeCropUseCase(repo)
    selection = use_case.resize(
        ResizeCropRequest(
            CropPosition.BOTTOM,
            CropHandle.SE,
            make_crop(0, 0, 100, 100),
            50,
            1.0,
            make_source(1000, 1000),
        ),
    )
    assert selection.bottom.w == 150.0
    assert isinstance(selection, CropSelection)
    assert repo.get() == selection
