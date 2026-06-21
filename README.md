# ARCGDLW — Gallery Downloader

A GUI + CLI tool to download media galleries via `gallery-dl`, optionally convert videos to GIF, and package the result into an archive.

## Features

- Download from any site supported by `gallery-dl`
- Convert short, silent videos to GIF automatically (via `ffmpeg`)
- Archive output as `.zip`, `.cbz`, `.rar`, or `.cbr`
- Dark-themed PyQt6 GUI with native folder picker
- CLI mode for scripting

## Requirements

**Python packages:**
```
pip install -r requirements.txt
```

**System tools** (must be on your PATH):
- [`gallery-dl`](https://github.com/mikf/gallery-dl)
- `ffmpeg` / `ffprobe`
- `rar` — optional, only needed for `.rar`/`.cbr` output

## Usage

### GUI
```bash
python main.py
```

### CLI
```bash
python main.py <url> [url2 ...] [options]

Options:
  -o, --output <folder>   Output folder (default: ./downloads)
  -f, --format <fmt>      Target format: gif, mp4, webm, mkv (default: gif)
  --override              Force conversion regardless of duration/audio rules
  --zip                   Archive as .zip
  --cbz                   Archive as .cbz (Comic Book Zip)
  --rar                   Archive as .rar
  --cbr                   Archive as .cbr (Comic Book Rar)
```

**Example:**
```bash
python main.py https://example.com/gallery -f gif --cbz -o ~/Pictures/downloads
```
