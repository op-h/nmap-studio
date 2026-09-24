"""Vector icons drawn with QPainter.

No SVG module and no image files: every icon is a handful of strokes on a
24x24 grid, so they stay crisp at any DPI and recolour with the theme.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_CACHE: dict[tuple, QIcon] = {}


def _poly(path: QPainterPath, points, close=True):
    path.moveTo(*points[0])
    for pt in points[1:]:
        path.lineTo(*pt)
    if close:
        path.closeSubpath()


def _draw(name: str, painter: QPainter, color: QColor) -> None:
    pen = QPen(color, 1.9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "play":
        path = QPainterPath()
        _poly(path, [(8, 5.5), (19, 12), (8, 18.5)])
        painter.fillPath(path, color)
    elif name == "stop":
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(6.5, 6.5, 11, 11), 2, 2)
    elif name == "pause":
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(7, 6, 3.6, 12), 1.4, 1.4)
        painter.drawRoundedRect(QRectF(13.4, 6, 3.6, 12), 1.4, 1.4)
    elif name == "plus":
        painter.drawLine(QPointF(12, 5.5), QPointF(12, 18.5))
        painter.drawLine(QPointF(5.5, 12), QPointF(18.5, 12))
    elif name == "close":
        painter.drawLine(QPointF(6.5, 6.5), QPointF(17.5, 17.5))
        painter.drawLine(QPointF(17.5, 6.5), QPointF(6.5, 17.5))
    elif name == "check":
        painter.drawPolyline([QPointF(5.5, 12.5), QPointF(10, 17), QPointF(18.5, 7)])
    elif name == "trash":
        painter.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
        painter.drawPolyline([QPointF(6.5, 7), QPointF(7.4, 19.5), QPointF(16.6, 19.5),
                              QPointF(17.5, 7)])
        painter.drawPolyline([QPointF(9.2, 7), QPointF(9.6, 4.5), QPointF(14.4, 4.5),
                              QPointF(14.8, 7)])
        painter.drawLine(QPointF(10.3, 10), QPointF(10.6, 16.5))
        painter.drawLine(QPointF(13.7, 10), QPointF(13.4, 16.5))
    elif name == "save":
        painter.drawPath(_rounded(3.8, 3.8, 16.4, 16.4, 2.5))
        painter.drawRect(QRectF(8, 3.8, 8, 5.4))
        painter.drawRect(QRectF(7.4, 13, 9.2, 7.2))
    elif name == "folder":
        painter.drawPolyline([QPointF(3.5, 18.5), QPointF(3.5, 5.5), QPointF(9.5, 5.5),
                              QPointF(11.5, 8), QPointF(20.5, 8), QPointF(20.5, 18.5),
                              QPointF(3.5, 18.5)])
    elif name == "export":
        painter.drawPolyline([QPointF(6, 14), QPointF(6, 19.5), QPointF(18, 19.5),
                              QPointF(18, 14)])
        painter.drawLine(QPointF(12, 3.5), QPointF(12, 14.5))
        painter.drawPolyline([QPointF(7.8, 8.2), QPointF(12, 3.8), QPointF(16.2, 8.2)])
    elif name == "download":
        painter.drawPolyline([QPointF(6, 14), QPointF(6, 19.5), QPointF(18, 19.5),
                              QPointF(18, 14)])
        painter.drawLine(QPointF(12, 3.5), QPointF(12, 14.5))
        painter.drawPolyline([QPointF(7.8, 10.2), QPointF(12, 14.6), QPointF(16.2, 10.2)])
    elif name == "search":
        # Shifted up-left so the handle does not drag the optical centre
        # down-right; at 15px that offset is what made it look misplaced.
        painter.drawEllipse(QPointF(10.2, 10.2), 6.0, 6.0)
        painter.drawLine(QPointF(14.6, 14.6), QPointF(19.0, 19.0))
    elif name == "settings":
        painter.save()
        painter.translate(12, 12)
        painter.drawEllipse(QPointF(0, 0), 3.2, 3.2)
        painter.drawEllipse(QPointF(0, 0), 6.6, 6.6)
        for _ in range(8):
            painter.drawLine(QPointF(0, -6.6), QPointF(0, -9.1))
            painter.rotate(45)
        painter.restore()
    elif name == "refresh":
        painter.drawArc(QRectF(4.5, 4.5, 15, 15), 95 * 16, 250 * 16)
        path = QPainterPath()
        _poly(path, [(18.6, 3.0), (19.8, 9.6), (13.4, 7.6)])
        painter.fillPath(path, color)
    elif name == "shield":
        painter.drawPolyline([QPointF(12, 3.4), QPointF(19.5, 6.4), QPointF(19.5, 12),
                              QPointF(12, 20.6), QPointF(4.5, 12), QPointF(4.5, 6.4),
                              QPointF(12, 3.4)])
    elif name == "server":
        painter.drawRoundedRect(QRectF(3.8, 4.4, 16.4, 6.2), 2, 2)
        painter.drawRoundedRect(QRectF(3.8, 13.4, 16.4, 6.2), 2, 2)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(7.4, 7.5), 1.0, 1.0)
        painter.drawEllipse(QPointF(7.4, 16.5), 1.0, 1.0)
    elif name == "network":
        painter.drawEllipse(QPointF(12, 12), 8.4, 8.4)
        painter.drawEllipse(QPointF(12, 12), 3.2, 8.4)
        painter.drawLine(QPointF(3.6, 12), QPointF(20.4, 12))
        painter.drawLine(QPointF(12, 3.6), QPointF(12, 20.4))
    elif name == "graph":
        # Three fat nodes and two links read as a network at 15px; five thin
        # ones just read as an X.
        painter.drawLine(QPointF(7.4, 7.0), QPointF(16.0, 13.4))
        painter.drawLine(QPointF(16.0, 13.4), QPointF(8.6, 18.4))
        painter.setBrush(color)
        for pt, r in (((6.6, 6.2), 3.4), ((17.0, 13.8), 3.0), ((8.0, 18.6), 2.8)):
            painter.drawEllipse(QPointF(*pt), r, r)
    elif name == "script":
        painter.drawPolyline([QPointF(6, 3.8), QPointF(15.5, 3.8), QPointF(19, 7.4),
                              QPointF(19, 20.2), QPointF(6, 20.2), QPointF(6, 3.8)])
        painter.drawLine(QPointF(9, 10), QPointF(16, 10))
        painter.drawLine(QPointF(9, 13.4), QPointF(16, 13.4))
        painter.drawLine(QPointF(9, 16.8), QPointF(13, 16.8))
    elif name == "terminal":
        painter.drawRoundedRect(QRectF(2.6, 4.4, 18.8, 15.2), 3.0, 3.0)
        painter.drawPolyline([QPointF(6.6, 9.6), QPointF(10.6, 12.2), QPointF(6.6, 14.8)])
        painter.drawLine(QPointF(12.6, 15.4), QPointF(17.4, 15.4))
    elif name == "copy":
        painter.drawRoundedRect(QRectF(8.4, 8.4, 11.2, 11.2), 2.2, 2.2)
        painter.drawPolyline([QPointF(15.6, 4.4), QPointF(4.4, 4.4), QPointF(4.4, 15.6)])
    elif name == "filter":
        painter.drawPolyline([QPointF(3.8, 5.4), QPointF(20.2, 5.4), QPointF(13.8, 12.6),
                              QPointF(13.8, 19.4), QPointF(10.2, 17.2),
                              QPointF(10.2, 12.6), QPointF(3.8, 5.4)])
    elif name == "compare":
        painter.drawLine(QPointF(12, 3.6), QPointF(12, 20.4))
        painter.drawPolyline([QPointF(7.4, 8.2), QPointF(3.6, 12), QPointF(7.4, 15.8)])
        painter.drawPolyline([QPointF(16.6, 8.2), QPointF(20.4, 12), QPointF(16.6, 15.8)])
    elif name == "clock":
        painter.drawEllipse(QPointF(12, 12), 8.4, 8.4)
        painter.drawPolyline([QPointF(12, 6.8), QPointF(12, 12.4), QPointF(16, 14.6)])
    elif name == "warning":
        painter.drawPolyline([QPointF(12, 3.8), QPointF(21, 19.6), QPointF(3, 19.6),
                              QPointF(12, 3.8)])
        painter.drawLine(QPointF(12, 9.6), QPointF(12, 14.4))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(12, 17.1), 1.0, 1.0)
    elif name == "info":
        painter.drawEllipse(QPointF(12, 12), 8.4, 8.4)
        painter.drawLine(QPointF(12, 11), QPointF(12, 16.4))
        painter.setBrush(color)
        painter.drawEllipse(QPointF(12, 7.9), 1.0, 1.0)
    elif name == "target":
        painter.drawEllipse(QPointF(12, 12), 8.0, 8.0)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(12, 12), 2.6, 2.6)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for a, b in (((12, 1.4), (12, 5.2)), ((12, 18.8), (12, 22.6)),
                     ((1.4, 12), (5.2, 12)), ((18.8, 12), (22.6, 12))):
            painter.drawLine(QPointF(*a), QPointF(*b))
    elif name == "star":
        path = QPainterPath()
        _poly(path, [(12, 3.6), (14.6, 9.4), (20.8, 10.1), (16.2, 14.3),
                     (17.5, 20.4), (12, 17.3), (6.5, 20.4), (7.8, 14.3),
                     (3.2, 10.1), (9.4, 9.4)])
        painter.fillPath(path, color)
    elif name == "star-outline":
        path = QPainterPath()
        _poly(path, [(12, 3.6), (14.6, 9.4), (20.8, 10.1), (16.2, 14.3),
                     (17.5, 20.4), (12, 17.3), (6.5, 20.4), (7.8, 14.3),
                     (3.2, 10.1), (9.4, 9.4)])
        painter.drawPath(path)
    elif name == "chevron-right":
        painter.drawPolyline([QPointF(9.5, 5.5), QPointF(16, 12), QPointF(9.5, 18.5)])
    elif name == "chevron-down":
        painter.drawPolyline([QPointF(5.5, 9.5), QPointF(12, 16), QPointF(18.5, 9.5)])
    elif name == "history":
        # A clock face with a rewind arrow. The old version was an open arc
        # that read as a crescent moon at tab size.
        painter.drawEllipse(QPointF(12.8, 12.8), 7.4, 7.4)
        painter.drawPolyline([QPointF(12.8, 8.4), QPointF(12.8, 13.0),
                              QPointF(16.2, 14.8)])
        path = QPainterPath()
        _poly(path, [(3.0, 4.4), (9.6, 5.6), (5.4, 10.6)])
        painter.fillPath(path, color)
    elif name == "sliders":
        # Two rails, two solid knobs. Three thin rails with hollow knobs turned
        # into a smudge at 16px.
        for y, x in ((8.4, 15.6), (15.6, 9.2)):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(3.6, y), QPointF(20.4, y))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 3.0, 3.0)
    elif name == "key":
        painter.drawEllipse(QPointF(8.2, 15.8), 4.4, 4.4)
        painter.drawLine(QPointF(11.4, 12.6), QPointF(20, 4))
        painter.drawLine(QPointF(17.2, 6.8), QPointF(19.4, 9))
        painter.drawLine(QPointF(14.6, 9.4), QPointF(16.8, 11.6))
    elif name == "lock":
        painter.drawRoundedRect(QRectF(5, 10.4, 14, 9.6), 2.2, 2.2)
        painter.drawArc(QRectF(8, 4, 8, 10), 0, 180 * 16)
    elif name == "eye":
        painter.drawPath(_eye())
        painter.drawEllipse(QPointF(12, 12), 2.6, 2.6)
    elif name == "code":
        painter.drawPolyline([QPointF(8.4, 7.6), QPointF(3.6, 12), QPointF(8.4, 16.4)])
        painter.drawPolyline([QPointF(15.6, 7.6), QPointF(20.4, 12), QPointF(15.6, 16.4)])
        painter.drawLine(QPointF(13.4, 5.6), QPointF(10.6, 18.4))
    elif name == "arrow-up":
        painter.drawLine(QPointF(12, 19.0), QPointF(12, 5.4))
        painter.drawPolyline([QPointF(6.6, 10.8), QPointF(12, 5.2), QPointF(17.4, 10.8)])
    elif name == "arrow-down":
        painter.drawLine(QPointF(12, 5.0), QPointF(12, 18.6))
        painter.drawPolyline([QPointF(6.6, 13.2), QPointF(12, 18.8), QPointF(17.4, 13.2)])
    elif name == "tick":
        pen.setWidthF(2.6)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(5.4, 12.6), QPointF(9.8, 17.0), QPointF(18.6, 7.2)])
    else:  # dot fallback
        painter.setBrush(color)
        painter.drawEllipse(QPointF(12, 12), 4, 4)


def _rounded(x, y, w, h, r) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path


def _eye() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(2.8, 12)
    path.quadTo(12, 4.4, 21.2, 12)
    path.quadTo(12, 19.6, 2.8, 12)
    return path


def app_icon() -> QIcon:
    """The application icon: the packaged PNGs if present, else the drawn mark."""
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    result = QIcon()
    found = False
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        path = os.path.join(assets, f"icon-{size}.png")
        if os.path.isfile(path):
            result.addFile(path, QSize(size, size))
            found = True
    return result if found else icon("network", "#3d8bfd", 256)


def icon(name: str, color: str = "#e6edf3", size: int = 24) -> QIcon:
    key = (name, color, size)
    if key in _CACHE:
        return _CACHE[key]
    pixmap = QPixmap(QSize(size, size) * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # The pixmap carries a 2x device pixel ratio, so the painter is already in
    # logical coordinates: scale by size/24, not by the pixel count.
    painter.scale(size / 24, size / 24)
    _draw(name, painter, QColor(color))
    painter.end()
    result = QIcon(pixmap)
    _CACHE[key] = result
    return result


def clear_cache() -> None:
    _CACHE.clear()
