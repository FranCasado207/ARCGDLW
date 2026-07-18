# ARCGDLW — Gallery Downloader

A Tauri + React desktop app (with an optional CLI) that wraps [`gallery-dl`](https://github.com/mikf/gallery-dl) to download media galleries from hundreds of websites, optionally convert short videos to high-quality GIF, and package the result into a zip, cbz, rar, or cbr archive.

---

## Architecture

The download/convert/archive logic is unchanged Python, but the UI is a native Tauri window instead of PyQt6:

```
┌─────────────────────────┐        HTTP + WebSocket        ┌──────────────────────────────┐
│  Tauri shell (Rust)      │ ───────── localhost only ────► │  Python backend (FastAPI)     │
│  - spawns the backend    │ ◄──────────────────────────────│  - task CRUD + persistence    │
│    as a sidecar process  │        (bearer-token auth)     │  - gallery-dl/ffmpeg/archive   │
│  - native dialogs/opener │                                 │  - live log/progress streams  │
│  - webview: React UI     │                                 │                                │
└─────────────────────────┘                                 └──────────────────────────────┘
```

- **`frontend/`** — React + TypeScript + Vite UI: Tasks, Download, and Config tabs, talking to the backend over REST + WebSocket (`frontend/src/api/`). Native folder/file pickers, "open in file manager", and notifications go through Tauri plugins (`frontend/src/lib/native.ts`) instead of backend subprocess calls.
- **`src-tauri/`** — the Rust shell. On startup it spawns the backend as an external ("sidecar") process, reads the port + auth token it prints on its first stdout lines, and hands them to the frontend via the `get_backend_info` command. The sidecar is killed when the window closes.
- **`src/arcgdlw/`** — the Python backend: `server.py` + `api/` (FastAPI app, task/download/config/settings endpoints), and the original `models/downloader`, `models/task`, `task_logs.py`, `app_settings.py`, `paths.py` — reused essentially unchanged from before the rewrite.

### Data storage

Settings, saved tasks, and preview thumbnails are stored per-user, outside the install/checkout directory, so they survive updates and work the same whether run from source or as a packaged app:

| Platform | Location |
|---|---|
| Linux | `$XDG_DATA_HOME/ARCGDLW` (defaults to `~/.local/share/ARCGDLW`) |
| Windows | `%APPDATA%\ARCGDLW` |
| macOS | `~/Library/Application Support/ARCGDLW` |

This directory contains `app_settings.json`, `tasks.json`, a `previews/` folder of thumbnail images, and a `logs/` folder of per-task run logs.

---

## Requirements

**To run from source:**

- Python ≥ 3.12, [`uv`](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/) ≥ 20, npm
- [Rust](https://www.rust-lang.org/tools/install) (stable) — needed to build/run the Tauri shell

**System tools** (must be available on your `PATH`):

| Tool | Purpose | Install |
|---|---|---|
| `gallery-dl` | Gallery downloading | [github.com/mikf/gallery-dl](https://github.com/mikf/gallery-dl) |
| `ffmpeg` | Video conversion / GIF encoding | [ffmpeg.org](https://ffmpeg.org/) |
| `ffprobe` | Video metadata inspection | Bundled with ffmpeg |
| `rar` | RAR/CBR archive creation | Proprietary; optional — only needed for `.rar`/`.cbr` output |

**Tauri build prerequisites** (Linux only, for compiling the Rust shell): see the [Tauri docs](https://v2.tauri.app/start/prerequisites/) — on Debian/Ubuntu this is `libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev libgtk-3-dev libxdo-dev libssl-dev patchelf build-essential`.

---

## Development

```bash
git clone https://github.com/FranCasado207/ARCGDLW.git
cd ARCGDLW

# Backend
python -m venv .venv && source .venv/bin/activate
pip install uv
uv pip install -r requirements.txt

# Frontend
npm install --prefix frontend
```

Run the backend and the Tauri app in two terminals:

```bash
# Terminal 1 — backend, fixed port/token matching frontend/.env.development
ARCGDLW_DEV_TOKEN=devtoken PYTHONPATH=src uv run python -m arcgdlw.main --serve --port 8734

# Terminal 2 — Tauri app (auto-starts the Vite dev server too)
npx --prefix frontend tauri dev
```

`npm run tauri dev` bundles and spawns its own backend sidecar as well (matching what a packaged build does), but the frontend in dev mode always talks to the manually-started backend above via `frontend/.env.development` — see `frontend/src/api/backend.ts`.

### CLI

Full feature parity with the app for one-shot downloads, scriptable without the GUI:

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

---

## How a download works

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

Each URL is processed in its own temp directory and cleaned up afterwards regardless of success or failure. Multiple URLs are processed sequentially with automatic retry (default: 3 attempts, 5s delay).

---

## Configuration

ARCGDLW reads the `gallery-dl` config file to pass through to `gallery-dl` (cookies, rate limits, filename templates, extractor options, etc.). The **Config tab** lets you view and edit this file directly without leaving the app.

**Auto-detected locations (in order):**

1. `~/.config/gallery-dl/config.json`
2. `~/.gallery-dl.conf`
3. `/etc/gallery-dl.conf`

You can also browse to a custom path from the Config tab — the choice is saved in `app_settings.json` (see [Data storage](#data-storage)).

---

## Building standalone installers

```bash
python scripts/build_sidecar.py       # builds the Python backend into src-tauri/binaries/
npx --prefix frontend tauri build     # builds + bundles the Tauri app
```

`scripts/build_sidecar.py` runs PyInstaller against `backend.spec` and copies the result into `src-tauri/binaries/` under the name Tauri's sidecar resolution expects (`arcgdlw-backend-<rust-target-triple>[.exe]`). `tauri build` then produces platform-native installers under `src-tauri/target/release/bundle/`: `.deb`/`.AppImage` (Linux), `.msi`/`.exe` (NSIS, Windows), `.dmg` (macOS).

`.github/workflows/build.yml` builds all of the above on a Linux/Windows/macOS (Intel + Apple Silicon) matrix on every push/PR to `main` and on `v*` tags, and attaches the installers to a GitHub Release for tagged builds.
