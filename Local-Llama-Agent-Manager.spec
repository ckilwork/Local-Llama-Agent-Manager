# -*- mode: python ; coding: utf-8 -*-
"""Reproducible Windows build; avoid unrelated ICU libraries on PATH."""

from pathlib import Path

source_dir = Path(SPECPATH)

a = Analysis(
    [str(source_dir / "main.py")],
    pathex=[str(source_dir)],
    binaries=[],
    datas=[(str(source_dir / "resources"), "resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Qt6Core.dll imports Windows' unversioned icuuc.dll. A different copy on PATH
# (for example Poppler's ICU 78) exports version-suffixed symbols instead and
# makes QtWidgets fail with WinError 127 when PyInstaller bundles it.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in {"icuuc.dll", "icudt78.dll"}]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Local-Llama-Agent-Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(source_dir / "Local-Llama-Agent-Manager-minimal.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Local-Llama-Agent-Manager",
)
