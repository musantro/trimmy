"""Static preset catalogue backing the :class:`PresetRepository` port."""

from __future__ import annotations

from trimmy.rendering.domain.models import (
    EncoderPreset,
    PlatformDisplayInfo,
    PlatformFormat,
)
from trimmy.rendering.domain.preset_repository import PresetRepository
from trimmy.shared.compat import override

_PRESETS: dict[str, dict[str, EncoderPreset]] = {
    "instagram": {
        "max": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.0",
            preset="slow",
            crf=16,
            maxrate="25000k",
            bufsize="50000k",
            max_fps=60,
            audio_bitrate="192k",
            max_size_mb=300,
            movflags="+faststart",
        ),
        "optimized": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.0",
            preset="medium",
            crf=23,
            maxrate="8000k",
            bufsize="16000k",
            max_fps=60,
            audio_bitrate="128k",
            max_size_mb=300,
            movflags="+faststart",
        ),
    },
    "tiktok": {
        "max": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.2",
            preset="slow",
            crf=16,
            maxrate="20000k",
            bufsize="40000k",
            max_fps=60,
            audio_bitrate="192k",
            max_size_mb=4096,
            movflags="+faststart",
        ),
        "optimized": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.2",
            preset="medium",
            crf=23,
            maxrate="8000k",
            bufsize="16000k",
            max_fps=60,
            audio_bitrate="128k",
            max_size_mb=4096,
            movflags="+faststart",
        ),
    },
    "twitter": {
        "max": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.2",
            preset="slow",
            crf=18,
            maxrate="15000k",
            bufsize="30000k",
            max_fps=60,
            audio_bitrate="192k",
            max_size_mb=512,
            movflags="+faststart",
        ),
        "optimized": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.2",
            preset="medium",
            crf=23,
            maxrate="5000k",
            bufsize="10000k",
            max_fps=60,
            audio_bitrate="128k",
            max_size_mb=512,
            movflags="+faststart",
        ),
    },
    "whatsapp": {
        "max": EncoderPreset(
            width=720,
            height=1280,
            profile="main",
            level="3.1",
            preset="slow",
            crf=20,
            maxrate=None,
            bufsize_mult=2,
            max_fps=30,
            audio_bitrate="128k",
            max_size_mb=16,
            movflags="+faststart",
        ),
        "optimized": EncoderPreset(
            width=720,
            height=1280,
            profile="main",
            level="3.1",
            preset="medium",
            crf=26,
            maxrate=None,
            bufsize_mult=2,
            max_fps=30,
            audio_bitrate="96k",
            max_size_mb=16,
            movflags="+faststart",
        ),
    },
    "telegram": {
        "max": EncoderPreset(
            width=1080,
            height=1920,
            profile="high",
            level="4.2",
            preset="slow",
            crf=18,
            maxrate="20000k",
            bufsize="40000k",
            max_fps=60,
            audio_bitrate="192k",
            max_size_mb=2048,
            movflags="+faststart",
        ),
        "optimized": EncoderPreset(
            width=1080,
            height=1920,
            profile="main",
            level="4.0",
            preset="medium",
            crf=23,
            maxrate="6000k",
            bufsize="12000k",
            max_fps=60,
            audio_bitrate="128k",
            max_size_mb=2048,
            movflags="+faststart",
        ),
    },
}

_INFO: dict[str, dict[str, PlatformDisplayInfo]] = {
    "instagram": {
        "max": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.0",
            bitrate="CRF 16, max 25 Mbps",
            max_fps=60,
            audio="AAC 192k",
            max_size="300 MB",
            note="Maximum quality, slow encode",
        ),
        "optimized": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.0",
            bitrate="CRF 23, max 8 Mbps",
            max_fps=60,
            audio="AAC 128k",
            max_size="300 MB",
            note="Fast upload, great visual quality",
        ),
    },
    "tiktok": {
        "max": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.2",
            bitrate="CRF 16, max 20 Mbps",
            max_fps=60,
            audio="AAC 192k",
            max_size="4 GB",
            note="Maximum headroom for TikTok re-encoding",
        ),
        "optimized": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.2",
            bitrate="CRF 23, max 8 Mbps",
            max_fps=60,
            audio="AAC 128k",
            max_size="4 GB",
            note="Fast upload, good quality after re-encoding",
        ),
    },
    "twitter": {
        "max": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.2",
            bitrate="CRF 18, max 15 Mbps",
            max_fps=60,
            audio="AAC 192k",
            max_size="512 MB",
            note="Highest quality X accepts",
        ),
        "optimized": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.2",
            bitrate="CRF 23, max 5 Mbps",
            max_fps=60,
            audio="AAC 128k",
            max_size="512 MB",
            note="Recommended per X dev docs",
        ),
    },
    "whatsapp": {
        "max": PlatformDisplayInfo(
            res="720x1280",
            codec="H.264 Main 3.1",
            bitrate="CRF 20, auto-capped to 16 MB",
            max_fps=30,
            audio="AAC 128k",
            max_size="16 MB",
            note="Best quality within size limit",
        ),
        "optimized": PlatformDisplayInfo(
            res="720x1280",
            codec="H.264 Main 3.1",
            bitrate="CRF 26, auto-capped to 16 MB",
            max_fps=30,
            audio="AAC 96k",
            max_size="16 MB",
            note="Smaller files, faster send",
        ),
    },
    "telegram": {
        "max": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 High 4.2",
            bitrate="CRF 18, max 20 Mbps",
            max_fps=60,
            audio="AAC 192k",
            max_size="2 GB",
            note="Full quality, 60fps preserved",
        ),
        "optimized": PlatformDisplayInfo(
            res="1080x1920",
            codec="H.264 Main 4.0",
            bitrate="CRF 23, max 6 Mbps",
            max_fps=60,
            audio="AAC 128k",
            max_size="2 GB",
            note="Fast streaming, good quality",
        ),
    },
}

_FORMATS: dict[str, tuple[PlatformFormat, ...]] = {
    "instagram": (
        PlatformFormat(key="feed", label="Feed", max_duration=3600),
        PlatformFormat(key="reels", label="Reels", max_duration=90),
        PlatformFormat(key="stories", label="Stories", max_duration=60),
    ),
    "tiktok": (PlatformFormat(key="video", label="Video", max_duration=600),),
    "twitter": (PlatformFormat(key="post", label="Post", max_duration=140),),
    "whatsapp": (
        PlatformFormat(key="chat", label="Chat", max_duration=None),
        PlatformFormat(key="status", label="Status", max_duration=30),
    ),
    "telegram": (PlatformFormat(key="message", label="Message", max_duration=None),),
}


class InMemoryPresetRepository(PresetRepository):
    """Serves the built-in platform catalogue from in-process tables."""

    @override
    def encoder_preset(self, platform: str, quality: str) -> EncoderPreset:
        """Return the encoder preset for *platform* and *quality*."""
        return _PRESETS[platform][quality]

    @override
    def display_info(self, platform: str, quality: str) -> PlatformDisplayInfo:
        """Return the display info for *platform* and *quality*."""
        return _INFO[platform][quality]

    @override
    def formats(self, platform: str) -> tuple[PlatformFormat, ...]:
        """Return the upload formats for *platform*."""
        return _FORMATS[platform]
