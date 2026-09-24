#!/usr/bin/env python3
"""Generate the application icon at every size the packagers need.

Draws the mark with QPainter (same vector language as the in-app icons), then
assembles a multi-resolution .ico for Windows.
"""
from __future__ import annotations

import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PyQt6.QtCore import QPointF, QRectF, Qt                      # noqa: E402
from PyQt6.QtGui import (QColor, QConicalGradient, QLinearGradient,  # noqa: E402
                         QPainter, QPen, QPixmap)
from PyQt6.QtWidgets import QApplication                          # noqa: E402

ASSETS = os.path.join(ROOT, "nmapgui", "assets")
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]

BG_TOP = "#3a8ef0"
BG_BOTTOM = "#14346e"
MARK = "#ffffff"
BLIP = "#6ef2c0"          # a host answering
BLIP_GLOW = "#6ef2c055"


def draw(size: int) -> QPixmap:
    """A radar sweep over a network: what the app actually does, in one mark."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size / 64, size / 64)

    # ---- the tile
    gradient = QLinearGradient(0, 0, 64, 64)
    gradient.setColorAt(0.0, QColor(BG_TOP))
    gradient.setColorAt(1.0, QColor(BG_BOTTOM))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)

    centre = QPointF(32, 32)

    # ---- the sweep, brightest at its leading edge
    sweep = QConicalGradient(centre, 38)
    sweep.setColorAt(0.00, QColor(255, 255, 255, 190))
    sweep.setColorAt(0.16, QColor(255, 255, 255, 40))
    sweep.setColorAt(0.34, QColor(255, 255, 255, 0))
    sweep.setColorAt(1.00, QColor(255, 255, 255, 0))
    painter.setBrush(sweep)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPie(QRectF(10, 10, 44, 44), 38 * 16, -118 * 16)

    # ---- radar rings and crosshair
    painter.setBrush(Qt.BrushStyle.NoBrush)
    ring = QPen(QColor(255, 255, 255, 235), 2.6)
    painter.setPen(ring)
    painter.drawEllipse(centre, 21.0, 21.0)

    faint = QPen(QColor(255, 255, 255, 120), 1.6)
    painter.setPen(faint)
    painter.drawEllipse(centre, 12.0, 12.0)
    painter.drawLine(QPointF(11, 32), QPointF(53, 32))
    painter.drawLine(QPointF(32, 11), QPointF(32, 53))

    # ---- the leading edge of the sweep
    edge = QPen(QColor(255, 255, 255, 220), 2.2)
    edge.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(edge)
    painter.drawLine(centre, QPointF(32 + 21 * math.cos(math.radians(-38)),
                                     32 + 21 * math.sin(math.radians(-38))))

    # ---- a host found, with its glow
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BLIP_GLOW))
    painter.drawEllipse(QPointF(41.5, 22.5), 6.2, 6.2)
    painter.setBrush(QColor(BLIP))
    painter.drawEllipse(QPointF(41.5, 22.5), 3.4, 3.4)

    # ---- two quieter ones already behind the sweep
    painter.setBrush(QColor(255, 255, 255, 150))
    painter.drawEllipse(QPointF(22.0, 40.5), 2.3, 2.3)
    painter.drawEllipse(QPointF(38.0, 43.0), 1.9, 1.9)

    painter.end()
    return pixmap


def main() -> int:
    app = QApplication([])  # noqa: F841  (must outlive the pixmaps)
    os.makedirs(ASSETS, exist_ok=True)
    written = []
    for size in SIZES:
        path = os.path.join(ASSETS, f"icon-{size}.png")
        draw(size).save(path, "PNG")
        written.append(path)
    draw(256).save(os.path.join(ASSETS, "icon.png"), "PNG")

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is not installed — skipping the .ico "
              "(needed only to build the Windows executable).")
        return 0

    frames = [Image.open(os.path.join(ASSETS, f"icon-{s}.png"))
              for s in (16, 24, 32, 48, 64, 128, 256)]
    frames[0].save(os.path.join(ASSETS, "icon.ico"), format="ICO",
                   sizes=[(f.width, f.height) for f in frames])
    print(f"wrote {len(written)} PNGs, icon.png and icon.ico in {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
