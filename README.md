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

## Architecture

Trimmy is organised with **domain-driven design** and **vertical slicing**.
The first level under `trimmy/` is the set of modules (bounded contexts); each
module is split into the three classic layers:

```
trimmy/
├── crop/            # selecting & constraining the two crop regions
│   ├── domain/          value objects, specifications, services, repository (ABC)
│   ├── application/     use cases
│   └── infrastructure/  adapters (in-memory repository)
├── trim/            # the time range and its segmentation
│   ├── domain/
│   ├── application/
│   └── infrastructure/
├── render/          # ffmpeg encoding of the split-crop video
│   ├── domain/          encoding rules, gateways (ABC), preset repository (ABC)
│   ├── application/     use cases (probe, render, segmented render)
│   └── infrastructure/  ffmpeg / ffprobe / preset-catalogue adapters
├── preferences/     # persisting the user's settings
│   ├── domain/
│   ├── application/
│   └── infrastructure/  JSON-file repository
├── shared/          # shared kernel: Specification & UseCase base classes
└── presentation/    # PySide6 widgets and the main window
```

Patterns in use:

- **Repository pattern** — abstract repositories (`CropSelectionRepository`,
  `PresetRepository`, `PreferencesRepository`) live in the domain layer; their
  concrete adapters live in `infrastructure/`.
- **Use Case pattern** — every application operation is a `UseCase` subclass
  with a single `execute()` method.
- **Specification pattern** — business rules (bounds checks, fps capping,
  dynamic-bitrate detection, …) are small composable `Specification` objects.

### Test coverage policy

The coverage gate is **100%**, enforced only on the **domain** and
**application** layers of every module. The infrastructure layers and the
PySide6 presentation layer are omitted by configuration (see
`[tool.coverage.run]` in `pyproject.toml`), so the gate measures business
logic exclusively.

## License

MIT
