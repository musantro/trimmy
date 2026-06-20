"""Pure domain services that compute ffmpeg encoding parameters."""

from __future__ import annotations

import math
from collections.abc import Sequence

from trimmy.editing.shared.domain.models import CropSelection, TrimRange
from trimmy.rendering.domain.models import (
    BitratePlan,
    DimensionPlan,
    EncoderPreset,
    FpsPlan,
    PlatformFormat,
    RenderSpec,
    Segment,
)
from trimmy.rendering.domain.specifications import (
    ExceedsMaxDurationSpecification,
    FpsCapRequiredSpecification,
)

_MIN_VIDEO_KBPS = 200
_DEFAULT_BUFSIZE_MULT = 2


class SegmentPlanner:
    """Splits a trim range into parts no longer than a maximum duration."""

    def plan(
        self,
        trim_range: TrimRange,
        max_duration: float | None,
    ) -> list[Segment]:
        """Return the ordered segments covering *trim_range*."""
        if max_duration is None or not ExceedsMaxDurationSpecification(
            max_duration,
        ).is_satisfied_by(trim_range):
            return [
                Segment(
                    index=1,
                    total=1,
                    start=trim_range.start,
                    end=trim_range.end,
                ),
            ]

        num_parts = math.ceil(trim_range.duration / max_duration)
        equal_part = trim_range.duration / num_parts
        segments: list[Segment] = []
        for i in range(num_parts):
            seg_start = trim_range.start + i * equal_part
            seg_end = min(
                trim_range.start + (i + 1) * equal_part,
                trim_range.end,
            )
            segments.append(
                Segment(
                    index=i + 1,
                    total=num_parts,
                    start=seg_start,
                    end=seg_end,
                ),
            )
        return segments


_NVENC_PRESET = {
    "slower": "p7",
    "slow": "p6",
    "medium": "p4",
    "fast": "p2",
    "veryfast": "p1",
}
_AMF_QUALITY = {
    "slower": "quality",
    "slow": "quality",
    "medium": "balanced",
    "fast": "speed",
    "veryfast": "speed",
}
_QSV_PRESET = {
    "slower": "veryslow",
    "slow": "slow",
    "medium": "medium",
    "fast": "fast",
    "veryfast": "veryfast",
}


def _even(value: float) -> int:
    """Round *value* down to the nearest even integer."""
    truncated = int(value)
    return truncated - (truncated % 2)


class DimensionPlanner:
    """Computes even-aligned crop and output dimensions."""

    def plan(
        self,
        crops: CropSelection,
        split_ratio: float,
        preset: EncoderPreset,
    ) -> DimensionPlan:
        """Return the dimension plan for the given crops and preset."""
        output_height = preset.height
        top_out_h = _even(output_height * split_ratio)
        bottom_out_h = _even(output_height - int(output_height * split_ratio))

        total = top_out_h + bottom_out_h
        if total != output_height:
            bottom_out_h += output_height - total

        top = crops.top
        bottom = crops.bottom
        return DimensionPlan(
            output_width=preset.width,
            top_x=int(top.x),
            top_y=int(top.y),
            top_w=_even(top.w),
            top_h=_even(top.h),
            top_out_h=top_out_h,
            bottom_x=int(bottom.x),
            bottom_y=int(bottom.y),
            bottom_w=_even(bottom.w),
            bottom_h=_even(bottom.h),
            bottom_out_h=bottom_out_h,
        )


class FpsPlanner:
    """Decides whether the output frame rate must be capped."""

    def plan(self, source_fps: float, preset: EncoderPreset) -> FpsPlan:
        """Return the fps filter suffix and output frame rate."""
        if FpsCapRequiredSpecification(preset.max_fps).is_satisfied_by(
            source_fps,
        ):
            return FpsPlan(
                filter_suffix=f",fps={preset.max_fps}",
                output_fps=float(preset.max_fps),
            )
        return FpsPlan(filter_suffix="", output_fps=source_fps)


class FilterGraphBuilder:
    """Builds the ffmpeg ``filter_complex`` that stacks the two crops."""

    def build(self, dimensions: DimensionPlan, fps_suffix: str) -> str:
        """Return the filter graph string for the dimension plan."""
        width = dimensions.output_width
        return (
            f"[0:v]crop={dimensions.top_w}:{dimensions.top_h}:"
            f"{dimensions.top_x}:{dimensions.top_y},"
            f"scale={width}:{dimensions.top_out_h}{fps_suffix}[top];"
            f"[0:v]crop={dimensions.bottom_w}:{dimensions.bottom_h}:"
            f"{dimensions.bottom_x}:{dimensions.bottom_y},"
            f"scale={width}:{dimensions.bottom_out_h}{fps_suffix}[bottom];"
            f"[top][bottom]vstack=inputs=2[out]"
        )


class BitratePlanner:
    """Resolves the maxrate/bufsize pair, computing it when size-bound."""

    def plan(self, preset: EncoderPreset, duration: float) -> BitratePlan:
        """Return the bitrate plan for *preset* over *duration* seconds."""
        maxrate = preset.maxrate
        bufsize = preset.bufsize
        if maxrate is not None and bufsize is not None:
            return BitratePlan(maxrate=maxrate, bufsize=bufsize)

        audio_kbps = int(preset.audio_bitrate.replace("k", ""))
        total_kbps = (preset.max_size_mb * 8 * 1024) / duration
        video_kbps = max(_MIN_VIDEO_KBPS, int(total_kbps - audio_kbps))
        mult = preset.bufsize_mult or _DEFAULT_BUFSIZE_MULT
        return BitratePlan(
            maxrate=f"{video_kbps}k",
            bufsize=f"{video_kbps * mult}k",
        )


class CodecArgsFactory:
    """Builds the codec-specific ffmpeg argument lists."""

    def cpu(self, preset: EncoderPreset) -> list[str]:
        """Return libx264 codec arguments for *preset*."""
        return [
            "-c:v",
            "libx264",
            "-preset",
            preset.preset,
            "-crf",
            str(preset.crf),
        ]

    def gpu(self, encoder: str, preset: EncoderPreset) -> list[str] | None:
        """Return hardware codec arguments, or ``None`` if unsupported."""
        crf = str(preset.crf)
        if encoder == "h264_nvenc":
            return [
                "-c:v",
                "h264_nvenc",
                "-preset",
                _NVENC_PRESET.get(preset.preset, "p4"),
                "-cq",
                crf,
                "-b:v",
                "0",
            ]
        if encoder == "h264_amf":
            quality = _AMF_QUALITY.get(preset.preset, "balanced")
            return [
                "-c:v",
                "h264_amf",
                "-quality",
                quality,
                "-rc",
                "cqp",
                "-qp_i",
                crf,
                "-qp_p",
                crf,
                "-qp_b",
                crf,
            ]
        if encoder == "h264_qsv":
            return [
                "-c:v",
                "h264_qsv",
                "-preset",
                _QSV_PRESET.get(preset.preset, "medium"),
                "-global_quality",
                crf,
            ]
        return None


class CommandBuilder:
    """Assembles the full ffmpeg command line for an encode."""

    def build(
        self,
        spec: RenderSpec,
        preset: EncoderPreset,
        filter_complex: str,
        codec_args: Sequence[str],
        bitrate: BitratePlan,
        *,
        gpu: bool,
    ) -> list[str]:
        """Return the ffmpeg argument vector for the encode."""
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(spec.trim.start),
            "-to",
            str(spec.trim.end),
            "-i",
            str(spec.source_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-map",
            "0:a?",
        ]
        cmd.extend(codec_args)
        level = "auto" if gpu else preset.level
        cmd.extend(
            [
                "-profile:v",
                preset.profile,
                "-level:v",
                level,
                "-maxrate",
                bitrate.maxrate,
                "-bufsize",
                bitrate.bufsize,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                preset.audio_bitrate,
                "-ac",
                "2",
                "-ar",
                "48000",
                "-movflags",
                preset.movflags,
                "-shortest",
                str(spec.output_path),
            ],
        )
        return cmd


class FormatSelector:
    """Selects a platform format by key, falling back to the first."""

    def select(
        self,
        formats: Sequence[PlatformFormat],
        key: str,
    ) -> PlatformFormat:
        """Return the format matching *key*, or the first available."""
        for fmt in formats:
            if fmt.key == key:
                return fmt
        return formats[0]
