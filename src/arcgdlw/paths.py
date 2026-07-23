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


def get_default_output_dir() -> Path:
    """Default download destination, offered to the frontend as an absolute
    starting point (instead of a relative "./downloads" the frontend would
    have no consistent way to resolve itself, and that would break opening
    the resulting files/folder from the OS file manager if the backend's
    working directory ever differs from wherever the app was launched)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("USERPROFILE", Path.home()))
    else:
        base = Path.home()
    return base / "Downloads" / APP_NAME


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
