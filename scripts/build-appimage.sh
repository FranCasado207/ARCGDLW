#!/usr/bin/env bash
# Builds the Linux AppImage locally, mirroring the build-linux job in
# .github/workflows/build.yml. Run from anywhere; paths are resolved
# relative to the repo root. Uses the project's .venv, same as normal dev setup.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found on PATH. Install it first (e.g. 'pip install uv')." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "==> Creating .venv"
  uv venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
# pyqtdarktheme's published metadata caps Requires-Python at <3.12 even
# though it works fine on 3.12; uv doesn't enforce that stale bound, pip does.
uv pip install -r requirements.txt
uv pip install pyinstaller

echo "==> Building executable"
pyinstaller main.spec

echo "==> Assembling AppDir"
rm -rf AppDir
mkdir -p AppDir/usr/bin
cp dist/ARCGDLW AppDir/usr/bin/ARCGDLW
cp assets/icon.png AppDir/ARCGDLW.png

cat > AppDir/ARCGDLW.desktop <<'EOF'
[Desktop Entry]
Name=ARCGDLW
Exec=ARCGDLW
Icon=ARCGDLW
Type=Application
Categories=Utility;
Terminal=false
EOF

ln -sf usr/bin/ARCGDLW AppDir/AppRun

echo "==> Building AppImage"
if [ ! -x appimagetool ]; then
  wget -q -O appimagetool https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x appimagetool
fi
# Extract-and-run avoids needing FUSE, which may not be available/configured locally.
./appimagetool --appimage-extract-and-run AppDir ARCGDLW-x86_64.AppImage

echo "==> Done: $repo_root/ARCGDLW-x86_64.AppImage"
