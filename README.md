# Trimmy

Vertical split-crop video editor. Take any video, pick two crop regions, stack them top-and-bottom into a 9:16 frame, and export optimized for social media.

## What it does

1. Open or drag-drop a video
2. Position two crop boxes on the source frame (TOP and BOTTOM)
3. Adjust the split ratio by dragging the red divider
4. Trim the timeline to the segment you want
5. Pick a platform and quality preset
6. Render — ffmpeg encodes a ready-to-upload vertical video

The output stacks the two crops vertically into a single 9:16 video, useful for reaction content, split-screen tutorials, gameplay + facecam, etc.

## Platform presets

| Platform  | Resolution | Max FPS | Max Size | Codec           |
|-----------|-----------|---------|----------|-----------------|
| Instagram | 1080x1920 | 60      | 300 MB   | H.264 High 4.0  |
| TikTok    | 1080x1920 | 60      | 4 GB     | H.264 High 4.2  |
| Twitter/X | 1080x1920 | 60      | 512 MB   | H.264 High 4.2  |
| WhatsApp  | 720x1280  | 30      | 16 MB    | H.264 Main 3.1  |
| Telegram  | 1080x1920 | 60      | 2 GB     | H.264 High 4.2  |

Each platform has **Max** (highest quality, slower encode) and **Optimized** (smaller files, faster encode) quality modes. WhatsApp auto-caps bitrate to fit the 16 MB limit.

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) and ffprobe in PATH
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Install

```bash
git clone https://github.com/musantro/trimmy.git
cd trimmy
uv sync
```

## Usage

```bash
uv run python -m trimmy
```

Or open a file directly:

```bash
uv run python -m trimmy path/to/video.mp4
```

## Keyboard shortcuts

| Key       | Action           |
|-----------|------------------|
| K         | Play / Pause     |
| J         | Seek back 5s     |
| L         | Seek forward 5s  |

## License

MIT
