# -*- mode: python ; coding: utf-8 -*-
#
# Builds the ARCGDLW backend (arcgdlw.main, CLI + --serve API server) into a
# single executable named per Tauri's sidecar convention once the
# target-triple suffix is appended by scripts/build_sidecar.py:
# arcgdlw-backend[-<target-triple>][.exe]. Unlike the old main.py GUI build,
# this bundles no assets - the icon lives under src-tauri/icons/ now and the
# backend never touches it.

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    # uvicorn resolves its actual loop/protocol implementations at runtime
    # (loop="auto", http="auto", ws="auto"), which PyInstaller's static
    # import scan doesn't see.
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.loops.uvloop',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='arcgdlw-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
