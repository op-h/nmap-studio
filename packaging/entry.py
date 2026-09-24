"""Entry point for the frozen (PyInstaller) build.

A package's __main__.py cannot be used directly as the PyInstaller script —
its relative imports have no parent package at that point — so the bundle
starts here instead.
"""
import sys

from nmapgui.app import main

if __name__ == "__main__":
    sys.exit(main())
