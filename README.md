# ARCGDLW — Gallery Downloader

A PyQt6 desktop app (with an optional CLI) that wraps [`gallery-dl`](https://github.com/mikf/gallery-dl) to download media galleries from hundreds of websites, optionally convert short videos to high-quality GIF, and package the result into a zip, cbz, rar, or cbr archive.

---

## Features

### GUI
- **Tasks tab** — save reusable download presets with names, status badges, progress bars, per-task logs, and thumbnail previews with hover pop-up
- **Download tab** — one-shot download without saving a task
- **Config tab** — in-app editor for the `gallery-dl` JSON config file, with auto-detection from standard paths and a one-click "Create Default Config" button

### Download engine
- Downloads from any site supported by `gallery-dl` (1000+ extractors)
- Processes each URL sequentially to avoid archive-naming collisions
- Automatic retry with configurable attempts and delay (default: 3 attempts, 5 s delay)
- Smart GIF conversion: videos ≤ 15 s with no audio track are converted to GIF; longer or audio-bearing clips are left untouched (overridable)
- Two-pass palette GIF generation via `ffmpeg` (palettegen → paletteuse) for optimal quality and color accuracy
- Archive output as `.zip`, `.cbz` (Comic Book Zip), `.rar`, or `.cbr` (Comic Book Rar)
- Auto-increments filenames to prevent overwriting existing files

### CLI
Full feature parity with the GUI via command-line arguments, making it scriptable and automation-friendly.

---

## Requirements

**Python ≥ 3.12**

```bash
pip install uv
uv pip install --system -r requirements.txt
```

> `pyqtdarktheme`'s published metadata caps `Requires-Python` at `<3.12`, even though it
> works fine on 3.12 — plain `pip install -r requirements.txt` will refuse to install it
> on 3.12. `uv` doesn't enforce that stale bound. (Drop `--system` if installing into an
> already-activated virtualenv.)

**System tools** (must be available on your `PATH`):

| Tool | Purpose | Install |
|---|---|---|
| `gallery-dl` | Gallery downloading | [github.com/mikf/gallery-dl](https://github.com/mikf/gallery-dl) |
| `ffmpeg` | Video conversion / GIF encoding | [ffmpeg.org](https://ffmpeg.org/) |
| `ffprobe` | Video metadata inspection | Bundled with ffmpeg |
| `rar` | RAR/CBR archive creation | Proprietary; optional — only needed for `.rar`/`.cbr` output |

**Optional (for native file pickers):**
- KDE: `kdialog`
- GNOME: `zenity`

---

## Installation

```bash
git clone https://github.com/FranCasado207/ARCGDLW.git
cd ARCGDLW
python -m venv .venv && source .venv/bin/activate
pip install uv
uv pip install -r requirements.txt
```

---

## Usage

### GUI (no arguments)

```bash
python main.py
```

Launches the desktop app. The window opens on the **Tasks** tab.

### CLI

```bash
python main.py <url> [url2 ...] [options]
```

| Option | Default | Description |
|---|---|---|
| `-o`, `--output <folder>` | `./downloads` | Destination folder for files or archives |
| `-f`, `--format <fmt>` | `gif` | Target format: `gif`, `mp4`, `webm`, `mkv` |
| `--override` | off | Force video conversion regardless of duration/audio rules |
| `--zip` | — | Archive as `.zip` |
| `--cbz` | — | Archive as `.cbz` (Comic Book Zip) |
| `--rar` | — | Archive as `.rar` (requires `rar` installed) |
| `--cbr` | — | Archive as `.cbr` (Comic Book Rar) |

Archive flags are mutually exclusive (pick one or none).

**Examples:**

```bash
# Download and auto-convert short clips to GIF, save flat files
python main.py https://example.com/gallery

# Download two galleries, convert to GIF, package each as CBZ
python main.py https://site-a.com/album https://site-b.com/album --cbz -o ~/Pictures/downloads

# Force-convert all video regardless of length or audio, save as ZIP
python main.py https://example.com/gallery --override --zip -f gif
```

---

## How it works

```
URL(s)
  │
  ▼
gallery-dl  ─────────────────────────────► downloaded files (in a temp dir)
  │
  ▼
ffprobe  ──────► video info (duration, fps, has_audio)
  │
  ▼  (if targetFormat = gif AND duration ≤ 15s AND no audio — or --override)
ffmpeg palettegen ──► ffmpeg paletteuse ──► .gif  (original video deleted)
  │
  ▼
Archive (zip/cbz/rar/cbr) ──► output folder
  OR
Flat files (collision-safe rename) ──► output folder
```

Each URL is processed in its own temp directory and cleaned up afterwards regardless of success or failure.

---

## Project structure

```
ARCGDLW/
├── main.py                       # Thin entry point — adds src/ to sys.path and delegates to arcgdlw.main
├── src/
│   └── arcgdlw/
│       ├── main.py               # CLI parser + GUI launcher
│       ├── ui.py                 # PyQt6 GUI (window, tabs, task cards, dialogs, workers)
│       ├── app_settings.py       # Persistent key-value settings (app_settings.json)
│       ├── paths.py              # Per-user app data dir + bundled resource path resolution
│       └── models/
│           ├── downloader/
│           │   └── downloader.py     # Core download, conversion, and archive logic
│           └── task/
│               ├── task.py           # Task dataclass + TaskStatus enum
│               └── task_manager.py   # Task CRUD + persistence (tasks.json)
├── requirements.txt
└── pyproject.toml
```

---

## Data storage

Settings, saved tasks, and preview thumbnails are stored per-user, outside the install/checkout directory, so they survive updates and work the same whether run from source or as a packaged executable:

| Platform | Location |
|---|---|
| Linux | `$XDG_DATA_HOME/ARCGDLW` (defaults to `~/.local/share/ARCGDLW`) |
| Windows | `%APPDATA%\ARCGDLW` |
| macOS | `~/Library/Application Support/ARCGDLW` |

This directory contains `app_settings.json`, `tasks.json`, and a `previews/` folder of thumbnail images.

---

## Configuration

ARCGDLW reads the `gallery-dl` config file to pass through to `gallery-dl` (cookies, rate limits, filename templates, extractor options, etc.). The **Config tab** in the GUI lets you view and edit this file directly without leaving the app.

**Auto-detected locations (in order):**

1. `~/.config/gallery-dl/config.json`
2. `~/.gallery-dl.conf`
3. `/etc/gallery-dl.conf`

You can also browse to a custom path from the Config tab — the choice is saved in `app_settings.json` (see [Data storage](#data-storage)).

To generate a default config skeleton:

```bash
gallery-dl --config-create
```

Or click **Create Default Config** in the Config tab.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `PyQt6` | ≥ 6.11 | GUI framework |
| `pyqtdarktheme` | ≥ 2.1 | Auto dark/light theme |

---

## Building standalone executables

A [PyInstaller](https://pyinstaller.org/) spec (`main.spec`) builds a single-file executable that bundles the `assets/` folder:

```bash
pip install pyinstaller
pyinstaller main.spec
```

This produces `dist/ARCGDLW` (Linux) or `dist/ARCGDLW.exe` (Windows).

`.github/workflows/build.yml` builds both on every push/PR to `main` and on `v*` tags, and additionally wraps the Linux binary into an `ARCGDLW-x86_64.AppImage` using [AppImageKit](https://github.com/AppImage/AppImageKit). Build artifacts are attached to the workflow run.
