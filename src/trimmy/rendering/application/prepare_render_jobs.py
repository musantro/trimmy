"""Prepare stable render jobs and reserve their eventual output files."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from trimmy.editing.crop.domain import CropSelection
from trimmy.editing.trim.domain import TrimRange
from trimmy.rendering.domain.models import RenderQueueItem, RenderSpec, RenderTarget
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.rendering.domain.services import FormatSelector, SegmentPlanner


@dataclass(frozen=True)
class EditSnapshot:
    """Render-relevant editor values captured before preparation."""

    source_path: Path
    trim: TrimRange
    crops: CropSelection
    split_ratio: float
    source_fps: float


class PrepareRenderJobs:
    """Expand targets without consulting widgets or choosing concrete adapters."""

    def __init__(self, presets: PresetRepository, exists: Callable[[Path], bool]):
        self._presets = presets
        self._exists = exists

    @staticmethod
    def output_name(source: Path, target: RenderTarget, suffix: int | None) -> str:
        """Return the shared generated filename for a target."""
        number = f"_{suffix}" if suffix is not None else ""
        return f"{source.stem}{number}_{target.key}.mp4"

    @staticmethod
    def output_paths(item: RenderQueueItem) -> tuple[Path, ...]:
        """Return all paths owned by a job, including its base reservation."""
        path = item.spec.output_path
        segments = SegmentPlanner().plan(item.spec.trim, item.max_duration)
        parts = (
            tuple(path.with_name(f"{path.stem}_part{s.index}.mp4") for s in segments)
            if len(segments) > 1
            else ()
        )
        return (path, *parts)

    def prepare(
        self,
        snapshot: EditSnapshot,
        targets: tuple[RenderTarget, ...],
        paths: tuple[Path, ...],
        *,
        reserved: frozenset[Path] = frozenset(),
        avoid_collisions: bool = False,
    ) -> tuple[RenderQueueItem, ...]:
        """Keep explicit CLI paths; number GUI paths around occupied outputs."""
        occupied = set(reserved)
        jobs: list[RenderQueueItem] = []
        for target, path in zip(targets, paths, strict=True):
            fmt = FormatSelector().select(
                self._presets.formats(target.platform), target.format_key
            )
            index = 0
            while True:
                candidate = (
                    path
                    if index == 0
                    else path.with_name(f"{path.stem}_{index}{path.suffix}")
                )
                spec = RenderSpec(
                    snapshot.source_path,
                    candidate,
                    snapshot.trim,
                    CropSelection(snapshot.crops.top, snapshot.crops.bottom),
                    snapshot.split_ratio,
                    target.platform,
                    target.quality,
                    snapshot.source_fps,
                )
                item = RenderQueueItem(target, spec, fmt.max_duration)
                outputs = self.output_paths(item)
                if not avoid_collisions or not any(
                    p in occupied or self._exists(p) for p in outputs
                ):
                    break
                index += 1
            occupied.update(outputs)
            jobs.append(item)
        return tuple(jobs)

    @staticmethod
    def same_jobs(
        left: tuple[RenderQueueItem, ...], right: tuple[RenderQueueItem, ...]
    ) -> bool:
        """Compare complete render intent, including crops, quality and paths."""
        return left == right
