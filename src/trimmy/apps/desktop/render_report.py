"""Present the rendering report independently of widgets and editor state."""

from trimmy.rendering.domain.models import RenderJobResult, RenderQueueResult


def render_report(result: RenderJobResult | RenderQueueResult) -> str:
    """Describe every planned output with its original identity and status."""
    rows: list[str] = []

    jobs = (
        [(entry.target.key, entry.result) for entry in result.entries]
        if isinstance(result, RenderQueueResult)
        else [(result.target.key if result.target else "", result)]
    )

    cuts: dict[tuple[object, ...], int] = {}
    for target, job in jobs:
        for outcome in job.outcomes:
            spec = outcome.spec

            target_label = target or (
                f"{spec.platform} / {spec.quality}" if spec else "Unknown target"
            )
            cut = outcome.cut_spec or spec
            identity = (
                (
                    cut.source_path,
                    cut.trim,
                    cut.crops.top,
                    cut.crops.bottom,
                    cut.split_ratio,
                )
                if cut
                else ()
            )
            cut_index = cuts.setdefault(identity, len(cuts) + 1)
            source = str(spec.source_path) if spec else "Unknown source"

            bounds = f"{spec.trim.start:g}–{spec.trim.end:g}s" if spec else ""

            if outcome.is_cancelled:
                status = "Cancelled"

            elif outcome.unattempted:
                status = "Unattempted"

            elif outcome.is_failed:
                status = "Failed"

            else:
                status = "Succeeded"

            rows.append(
                f"Cut {cut_index}: {source} | {target_label} | "
                f"segment {outcome.index}/{outcome.total} ({bounds}): {status}"
                f"\n  {outcome.path or ''}"
                f"\n  {outcome.error or ''}",
            )

    return "\n\n".join(rows)
