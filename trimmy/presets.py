PLATFORM_PRESETS = {
    "instagram": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.0", "preset": "slow",
            "crf": 16, "maxrate": "25000k", "bufsize": "50000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 300, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.0", "preset": "medium",
            "crf": 23, "maxrate": "8000k", "bufsize": "16000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 300, "movflags": "+faststart",
        },
    },
    "tiktok": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 16, "maxrate": "20000k", "bufsize": "40000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 4096, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "medium",
            "crf": 23, "maxrate": "8000k", "bufsize": "16000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 4096, "movflags": "+faststart",
        },
    },
    "twitter": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 18, "maxrate": "15000k", "bufsize": "30000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 512, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "medium",
            "crf": 23, "maxrate": "5000k", "bufsize": "10000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 512, "movflags": "+faststart",
        },
    },
    "whatsapp": {
        "max": {
            "width": 720, "height": 1280,
            "profile": "main", "level": "3.1", "preset": "slow",
            "crf": 20, "maxrate": None, "bufsize_mult": 2,
            "max_fps": 30, "audio_bitrate": "128k",
            "max_size_mb": 16, "movflags": "+faststart",
        },
        "optimized": {
            "width": 720, "height": 1280,
            "profile": "main", "level": "3.1", "preset": "medium",
            "crf": 26, "maxrate": None, "bufsize_mult": 2,
            "max_fps": 30, "audio_bitrate": "96k",
            "max_size_mb": 16, "movflags": "+faststart",
        },
    },
    "telegram": {
        "max": {
            "width": 1080, "height": 1920,
            "profile": "high", "level": "4.2", "preset": "slow",
            "crf": 18, "maxrate": "20000k", "bufsize": "40000k",
            "max_fps": 60, "audio_bitrate": "192k",
            "max_size_mb": 2048, "movflags": "+faststart",
        },
        "optimized": {
            "width": 1080, "height": 1920,
            "profile": "main", "level": "4.0", "preset": "medium",
            "crf": 23, "maxrate": "6000k", "bufsize": "12000k",
            "max_fps": 60, "audio_bitrate": "128k",
            "max_size_mb": 2048, "movflags": "+faststart",
        },
    },
}

PLATFORM_INFO = {
    "instagram": {
        "max": {
            "res": "1080x1920", "codec": "H.264 High 4.0",
            "bitrate": "CRF 16, max 25 Mbps", "maxFps": 60,
            "audio": "AAC 192k", "maxSize": "300 MB",
            "note": "Maximum quality, slow encode",
        },
        "optimized": {
            "res": "1080x1920", "codec": "H.264 High 4.0",
            "bitrate": "CRF 23, max 8 Mbps", "maxFps": 60,
            "audio": "AAC 128k", "maxSize": "300 MB",
            "note": "Fast upload, great visual quality",
        },
    },
    "tiktok": {
        "max": {
            "res": "1080x1920", "codec": "H.264 High 4.2",
            "bitrate": "CRF 16, max 20 Mbps", "maxFps": 60,
            "audio": "AAC 192k", "maxSize": "4 GB",
            "note": "Maximum headroom for TikTok re-encoding",
        },
        "optimized": {
            "res": "1080x1920", "codec": "H.264 High 4.2",
            "bitrate": "CRF 23, max 8 Mbps", "maxFps": 60,
            "audio": "AAC 128k", "maxSize": "4 GB",
            "note": "Fast upload, good quality after re-encoding",
        },
    },
    "twitter": {
        "max": {
            "res": "1080x1920", "codec": "H.264 High 4.2",
            "bitrate": "CRF 18, max 15 Mbps", "maxFps": 60,
            "audio": "AAC 192k", "maxSize": "512 MB",
            "note": "Highest quality X accepts",
        },
        "optimized": {
            "res": "1080x1920", "codec": "H.264 High 4.2",
            "bitrate": "CRF 23, max 5 Mbps", "maxFps": 60,
            "audio": "AAC 128k", "maxSize": "512 MB",
            "note": "Recommended per X dev docs",
        },
    },
    "whatsapp": {
        "max": {
            "res": "720x1280", "codec": "H.264 Main 3.1",
            "bitrate": "CRF 20, auto-capped to 16 MB", "maxFps": 30,
            "audio": "AAC 128k", "maxSize": "16 MB",
            "note": "Best quality within size limit",
        },
        "optimized": {
            "res": "720x1280", "codec": "H.264 Main 3.1",
            "bitrate": "CRF 26, auto-capped to 16 MB", "maxFps": 30,
            "audio": "AAC 96k", "maxSize": "16 MB",
            "note": "Smaller files, faster send",
        },
    },
    "telegram": {
        "max": {
            "res": "1080x1920", "codec": "H.264 High 4.2",
            "bitrate": "CRF 18, max 20 Mbps", "maxFps": 60,
            "audio": "AAC 192k", "maxSize": "2 GB",
            "note": "Full quality, 60fps preserved",
        },
        "optimized": {
            "res": "1080x1920", "codec": "H.264 Main 4.0",
            "bitrate": "CRF 23, max 6 Mbps", "maxFps": 60,
            "audio": "AAC 128k", "maxSize": "2 GB",
            "note": "Fast streaming, good quality",
        },
    },
}
