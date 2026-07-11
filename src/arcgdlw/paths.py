import os
import sys
from pathlib import Path

APP_NAME = "ARCGDLW"


def get_app_data_dir() -> Path:
    """Per-user directory where ARCGDLW stores persistent data (settings,
    tasks, preview thumbnails). Works the same whether run from source or
    as a frozen PyInstaller executable, since __file__ is not reliable in
    the latter case (onefile builds extract to an ephemeral temp dir).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def resource_path(*parts: str) -> Path:
    """Resolve a bundled, read-only resource (e.g. an icon), working both
    when run from source and when frozen by PyInstaller (which extracts
    data files under sys._MEIPASS).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base.joinpath(*parts)


def subprocess_env() -> dict:
    """Environment for launching external tools (gallery-dl, ffmpeg, rar,
    kdialog, xdg-open, ...).

    PyInstaller's onefile Linux/macOS bootloader points *LD_LIBRARY_PATH*
    (or *DYLD_LIBRARY_PATH*) at its own bundled libs for the lifetime of the
    frozen process, and that leaks into every subprocess by default. A
    system binary launched with that environment can end up loading the
    bundled OpenSSL/zlib/etc. instead of its own and crash immediately
    (exit status 1, no useful error) — this is what happens to gallery-dl
    when run from the AppImage. PyInstaller preserves the original value
    (if any) under a *_ORIG suffix, so restore that instead.
    """
    env = os.environ.copy()
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        orig = env.pop(f"{var}_ORIG", None)
        if orig is not None:
            env[var] = orig
        else:
            env.pop(var, None)
    return env
