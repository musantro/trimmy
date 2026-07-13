# Install

Trimmy is a Python desktop application. The command you run is small, but it opens a full PySide6 editor.

## Requirements

You need:

* Python 3.10 or newer.
* `ffmpeg` on your `PATH`.
* `ffprobe` on your `PATH`.

Check ffmpeg:

```bash
ffmpeg -version
ffprobe -version
```

If either command is missing, install ffmpeg first.

=== "Windows"

    ```powershell
    winget install Gyan.FFmpeg
    ```

=== "macOS"

    ```bash
    brew install ffmpeg
    ```

=== "Linux"

    ```bash
    sudo apt install ffmpeg
    ```

## Install with pip

```bash
pip install trimmy
```

Then launch:

```bash
trimmy
```

## Run with uvx

If you use [uv](https://docs.astral.sh/uv/), you can run Trimmy without installing it into your current environment:

```bash
uvx trimmy
```

Open a video directly:

```bash
uvx trimmy "E:\musan\Videos\2026-06-08 23-52-54.mkv"
```

## From source

```bash
git clone https://github.com/musantro/trimmy.git
cd trimmy
uv sync
uv run trimmy
```

For development, run the test suite:

```bash
uv run pytest
```
