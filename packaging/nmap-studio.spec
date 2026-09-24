# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Nmap Studio.

Builds a single self-contained executable:

    Windows:  pyinstaller packaging/nmap-studio.spec    ->  dist/NmapStudio.exe
    Linux:    pyinstaller packaging/nmap-studio.spec    ->  dist/nmap-studio

The person running it still needs nmap installed; this bundles the interface
and Python, not the scanner.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
IS_WINDOWS = sys.platform.startswith("win")

datas = [(os.path.join(ROOT, "nmapgui", "assets"), "nmapgui/assets")]

from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs("PyQt6")

hiddenimports = ["PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
                 "PyQt6.QtPrintSupport", "PyQt6.QtNetwork"]
try:                                   # only present if the user installed it
    import winpty                      # noqa: F401
    hiddenimports.append("winpty")
except Exception:
    pass

excludes = [
    "tkinter", "unittest", "pydoc_data", "test",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtQml",
    "PyQt6.QtQuick", "PyQt6.QtMultimedia", "PyQt6.Qt3DCore", "PyQt6.QtCharts",
    "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSql",
    "PyQt6.QtTest", "PyQt6.QtDesigner", "PyQt6.QtHelp",
    "matplotlib", "numpy", "scipy", "pandas",
]

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NmapStudio" if IS_WINDOWS else "nmap-studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,                       # no console window behind the GUI
    disable_windowed_traceback=False,
    icon=(os.path.join(ROOT, "nmapgui", "assets", "icon.ico")
          if IS_WINDOWS else None),
)
