from trimmy.renderer import CropRect


def make_crop_rect(x=0.0, y=0.0, w=100.0, h=100.0):
    return CropRect(x=x, y=y, w=w, h=h)


def make_video_info(duration=60.0, width=1920, height=1080, fps=30.0, path=None):
    info = {"duration": duration, "width": width, "height": height, "fps": fps}
    if path is not None:
        info["path"] = path
    return info


def make_preset(width=1080, height=1920, profile="high", level="4.0",
                preset="slow", crf=16, maxrate="25000k", bufsize="50000k",
                max_fps=60, audio_bitrate="192k", max_size_mb=300,
                movflags="+faststart"):
    return {
        "width": width, "height": height, "profile": profile, "level": level,
        "preset": preset, "crf": crf, "maxrate": maxrate, "bufsize": bufsize,
        "max_fps": max_fps, "audio_bitrate": audio_bitrate,
        "max_size_mb": max_size_mb, "movflags": movflags,
    }
