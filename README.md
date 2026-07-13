# Trimmy

**Vertical split-crop video editor.** Take any video, pick two crop regions, stack them top-and-bottom into a 9:16 frame, and export optimized for social media.

The output stacks the two crops vertically into a single 9:16 video — ideal for reaction content, split-screen tutorials, gameplay + facecam, and Reels / TikToks / Shorts.

## Install

```bash
pip install trimmy
```

Or run it without installing, using [uv](https://docs.astral.sh/uv/):

```bash
uvx trimmy
```

> **Requires** [ffmpeg](https://ffmpeg.org/) and `ffprobe` available on your `PATH`, plus Python 3.10+.

## Usage

Launch the app:

```bash
trimmy
```

Or open a file directly:

```bash
trimmy path/to/video.mp4
```

Then:

1. Open or drag-drop a video.
2. Position the two crop boxes on the source frame (**TOP** and **BOTTOM**).
3. Adjust the split ratio by dragging the red divider.
4. Trim the timeline to the segment you want.
5. Pick a platform and quality preset.
6. Render — ffmpeg encodes a ready-to-upload vertical video.

### Keyboard shortcuts

| Key | Action                     |
|-----|----------------------------|
| K   | Play / Pause               |
| J   | Seek backward 5s           |
| L   | Seek forward 5s            |
| Q   | Set trim start to playhead |
| E   | Set trim end to playhead   |
| M   | Toggle mute                |
| ?   | Show keyboard shortcuts    |

## Platform presets

| Platform  | Resolution | Max FPS | Max Size | Codec          |
|-----------|------------|---------|----------|----------------|
| Instagram | 1080x1920  | 60      | 300 MB   | H.264 High 4.0 |
| TikTok    | 1080x1920  | 60      | 4 GB     | H.264 High 4.2 |
| Twitter/X | 1080x1920  | 60      | 512 MB   | H.264 High 4.2 |
| WhatsApp  | 720x1280   | 30      | 16 MB    | H.264 Main 3.1 |
| Telegram  | 1080x1920  | 60      | 2 GB     | H.264 High 4.2 |

Each platform offers a **Max** mode (highest quality, slower encode) and an **Optimized** mode (smaller files, faster encode). WhatsApp auto-caps bitrate to fit the 16 MB limit.

## Development

Trimmy is built with [PySide6](https://doc.qt.io/qtforpython/). To work on it
from source:

```bash
git clone https://github.com/musantro/trimmy.git
cd trimmy
uv sync
uv run python -m trimmy
```

See [CHANGELOG.md](https://github.com/musantro/trimmy/blob/master/CHANGELOG.md)
for release history.

## Documentation

The documentation site lives in [docs](docs) and is configured with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/):

```bash
uv run --group docs mkdocs serve
```

## License

[MIT](https://github.com/musantro/trimmy/blob/master/README.md)
</content>
</invoke>
