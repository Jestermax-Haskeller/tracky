# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for a single-file, no-console Windows executable."""

from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("pywinauto") + collect_submodules("comtypes")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets/tracky.ico", "assets")],
    hiddenimports=hidden,
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
    name="tracky",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/tracky.ico",
    version="version_info.txt",
)
