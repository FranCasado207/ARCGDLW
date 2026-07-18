#!/usr/bin/env python3
"""Builds the Python backend into the Tauri sidecar binary.

Runs PyInstaller against backend.spec, then copies the result into
src-tauri/binaries/ under the name Tauri's sidecar resolution expects:
arcgdlw-backend-<rust-target-triple>[.exe]. Used both by CI (one job per OS)
and locally before `tauri dev` / `tauri build`.
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rust_target_triple() -> str:
    result = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not determine the Rust host target triple from `rustc -vV`")


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "backend.spec", "--noconfirm"],
        cwd=ROOT,
        check=True,
    )

    triple = rust_target_triple()
    suffix = ".exe" if platform.system() == "Windows" else ""
    built = ROOT / "dist" / f"arcgdlw-backend{suffix}"
    if not built.exists():
        raise FileNotFoundError(f"expected PyInstaller output at {built}, but it doesn't exist")

    dest_dir = ROOT / "src-tauri" / "binaries"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"arcgdlw-backend-{triple}{suffix}"
    shutil.copy2(built, dest)
    if suffix == "":
        dest.chmod(0o755)

    print(f"Sidecar binary ready: {dest}")


if __name__ == "__main__":
    main()
