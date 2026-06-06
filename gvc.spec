# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import copy_metadata

ROOT = Path(globals().get("SPECPATH", ".")).resolve()
ASSETS_DIR = ROOT / "Assets"
BIN_DIR = ROOT / "bin"

datas = [
    (str(ASSETS_DIR / "icon.png"), "Assets"),
    (str(ASSETS_DIR / "icon.ico"), "Assets"),
]
datas += copy_metadata("godot-video-converter-py")

binaries = []
icon_path = ASSETS_DIR / "icon.png"

if sys.platform == "win32":
    ffmpeg_path = BIN_DIR / "ffmpeg.exe"
    ffprobe_path = BIN_DIR / "ffprobe.exe"
    missing = [str(path) for path in (ffmpeg_path, ffprobe_path) if not path.exists()]
    if missing:
        raise SystemExit(
            "Missing required Windows binaries for packaging: " + ", ".join(missing)
        )
    binaries = [
        (str(ffmpeg_path), "bin"),
        (str(ffprobe_path), "bin"),
    ]
    icon_path = ASSETS_DIR / "icon.ico"


a = Analysis(
    ["src/gvc/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='gvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(icon_path)],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='gvc',
)
