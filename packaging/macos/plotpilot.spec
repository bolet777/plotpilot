# PyInstaller spec: builds dist/PlotPilot.app (run from repo root via scripts/build_macos_app.sh).
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent
SRC = ROOT / "src"
ICNS = ROOT / "assets" / "icons" / "plotpilot.icns"
ICON_DATAS = SRC / "plotpilot" / "resources" / "icons"

a = Analysis(
    [str(Path(SPECPATH) / "entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(ICON_DATAS), "plotpilot/resources/icons")],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "Foundation",
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
    [],
    exclude_binaries=True,
    name="PlotPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PlotPilot",
)

app = BUNDLE(
    coll,
    name="PlotPilot.app",
    icon=str(ICNS),
    bundle_identifier="com.plotpilot.app",
    info_plist={
        "CFBundleName": "PlotPilot",
        "CFBundleDisplayName": "PlotPilot",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
