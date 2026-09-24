"""Radial network map built from scan results and traceroute data."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (QCheckBox, QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene,
                             QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from .. import icons
from ..design import HIT, RADIUS, SPACE, TYPE
from ..parser import Host, ScanResult


class HostNode(QGraphicsEllipseItem):
    def __init__(self, ip: str, host: Host | None, radius: float, pal: dict, kind: str):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.ip = ip
        self.host = host
        self.pal = pal
        self.kind = kind          # "self" | "host" | "hop"
        self.radius = radius
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)

        tip = [ip]
        if host is not None:
            if host.hostname:
                tip.append(host.hostname)
            tip.append(f"{len(host.open_ports)} open ports")
            if host.best_os:
                tip.append(f"OS: {host.best_os} ({host.os_accuracy}%)")
            top = ", ".join(f"{p.portid}/{p.service.name or p.protocol}"
                            for p in host.open_ports[:8])
            if top:
                tip.append(top)
        else:
            tip.append("intermediate hop")
        self.setToolTip("\n".join(tip))

    def _colour(self) -> str:
        if self.kind == "self":
            return self.pal["accent"]
        if self.kind == "hop":
            return self.pal["faint"]
        if self.host is None or self.host.state != "up":
            return self.pal["closed"]
        count = len(self.host.open_ports)
        if count == 0:
            return self.pal["filtered"]
        return self.pal["open"] if count < 8 else self.pal["purple"]

    def _apply_style(self, hover: bool) -> None:
        colour = QColor(self._colour())
        gradient = QRadialGradient(QPointF(0, -self.radius * 0.35), self.radius * 1.7)
        gradient.setColorAt(0.0, colour.lighter(150 if hover else 125))
        gradient.setColorAt(1.0, colour.darker(150))
        self.setBrush(QBrush(gradient))
        pen = QPen(colour.lighter(160 if hover else 110), 2.4 if hover else 1.4)
        self.setPen(pen)

    def hoverEnterEvent(self, event):
        self._apply_style(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._apply_style(False)
        super().hoverLeaveEvent(event)


class TopologyView(QWidget):
    """Concentric rings: you in the middle, hops outward, hosts on the rim."""

    host_clicked = pyqtSignal(str)

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.result: ScanResult | None = None
        self._user_zoomed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACE["sm"])

        bar = QHBoxLayout()
        bar.setContentsMargins(0, SPACE["md"], 0, 0)
        bar.setSpacing(SPACE["md"])
        self.labels = QCheckBox("Labels", self)
        self.labels.setChecked(True)
        self.labels.toggled.connect(lambda *_: self.refresh(self.result))
        bar.addWidget(self.labels)
        self.show_down = QCheckBox("Include down hosts", self)
        self.show_down.toggled.connect(lambda *_: self.refresh(self.result))
        bar.addWidget(self.show_down)
        bar.addStretch(1)
        for label, tip, handler in (("Fit", "Fit the whole map", self.fit),
                                    ("+", "Zoom in", lambda: self.zoom(1.25)),
                                    ("−", "Zoom out", lambda: self.zoom(0.8))):
            btn = QPushButton(label, self)
            btn.setProperty("flat", "true")
            btn.setToolTip(tip)
            btn.setMinimumSize(HIT["comfortable"] + 8, HIT["min"])
            btn.clicked.connect(handler)
            bar.addWidget(btn)
        root.addLayout(bar)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHints(QPainter.RenderHint.Antialiasing |
                                 QPainter.RenderHint.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QBrush(QColor(pal["term_bg"])))
        self.view.setStyleSheet(
            f"QGraphicsView{{border:1px solid {pal['line']};"
            f"border-radius:{RADIUS['panel']}px;}}")
        self.view.mousePressEvent = self._mouse_press  # type: ignore[assignment]
        self.view.wheelEvent = self._wheel  # type: ignore[assignment]
        root.addWidget(self.view, 1)

        legend = self.legend = QLabel(self)
        legend.setProperty("role", "dim")
        legend.setContentsMargins(SPACE["xs"], 0, SPACE["xs"], SPACE["xs"])
        legend.setStyleSheet(f"color:{pal['faint']};font-size:{TYPE['small']}px;")
        legend.setText(
            f'<span style="color:{pal["accent"]}">●</span> this machine &nbsp;'
            f'<span style="color:{pal["faint"]}">●</span> hop &nbsp;'
            f'<span style="color:{pal["open"]}">●</span> host with open ports &nbsp;'
            f'<span style="color:{pal["purple"]}">●</span> 8+ open ports &nbsp;'
            f'<span style="color:{pal["filtered"]}">●</span> up, no open ports &nbsp;'
            f'<span style="color:{pal["closed"]}">●</span> down &nbsp;&nbsp;'
            "— drag to pan, scroll to zoom, click a node to select it")
        root.addWidget(legend)

    def restyle(self) -> None:
        pal = self.pal
        self.view.setBackgroundBrush(QBrush(QColor(pal["term_bg"])))
        self.view.setStyleSheet(
            f"QGraphicsView{{border:1px solid {pal['line']};"
            f"border-radius:{RADIUS['panel']}px;}}")
        self.legend.setStyleSheet(f"color:{pal['faint']};font-size:{TYPE['small']}px;")
        self.refresh(self.result)

    # ------------------------------------------------------------------ build
    def refresh(self, result: ScanResult | None) -> None:
        self.result = result
        self.scene.clear()
        if result is None or not result.hosts:
            self._empty()
            return

        hosts = [h for h in result.hosts
                 if self.show_down.isChecked() or h.state == "up"]
        if not hosts:
            self._empty()
            return

        # Build a tree: localhost -> (hops…) -> host
        children: dict[str, list[str]] = {"localhost": []}
        node_host: dict[str, Host | None] = {"localhost": None}
        parent_of: dict[str, str] = {}

        def link(parent: str, child: str) -> None:
            children.setdefault(parent, [])
            children.setdefault(child, [])
            if child not in children[parent]:
                children[parent].append(child)
                parent_of[child] = parent

        for host in hosts:
            chain = [hop.ipaddr for hop in host.trace if hop.ipaddr and hop.ipaddr != host.ip]
            previous = "localhost"
            for hop_ip in chain:
                node_host.setdefault(hop_ip, None)
                if hop_ip not in parent_of:
                    link(previous, hop_ip)
                previous = hop_ip
            node_host[host.ip] = host
            if host.ip not in parent_of:
                link(previous, host.ip)

        levels: dict[str, int] = {"localhost": 0}
        order: list[str] = ["localhost"]
        queue = ["localhost"]
        while queue:
            current = queue.pop(0)
            for child in children.get(current, []):
                if child not in levels:
                    levels[child] = levels[current] + 1
                    order.append(child)
                    queue.append(child)

        # A radial tree: every subtree owns a wedge sized by how many leaves it
        # holds, so branches fan out instead of crossing over each other.
        leaves: dict[str, int] = {}

        def count_leaves(name: str) -> int:
            kids = [c for c in children.get(name, []) if levels.get(c, 0) > levels[name]]
            leaves[name] = max(1, sum(count_leaves(c) for c in kids)) if kids else 1
            return leaves[name]

        count_leaves("localhost")

        ring = 165
        positions: dict[str, QPointF] = {"localhost": QPointF(0, 0)}
        deepest = max(levels.values()) if levels else 0

        def place(name: str, start: float, end: float) -> None:
            kids = [c for c in children.get(name, []) if levels.get(c, 0) > levels[name]]
            if not kids:
                return
            total = sum(leaves[c] for c in kids)
            cursor = start
            for child in kids:
                span = (end - start) * leaves[child] / total
                angle = cursor + span / 2
                radius = ring * levels[child]
                positions[child] = QPointF(radius * math.cos(angle), radius * math.sin(angle))
                place(child, cursor, cursor + span)
                cursor += span

        place("localhost", -math.pi / 2, 3 * math.pi / 2)

        by_level: dict[int, list[str]] = {}
        for name in order:
            by_level.setdefault(levels[name], []).append(name)

        # rings
        for level in sorted(by_level):
            if level == 0:
                continue
            radius = ring * level
            ring_item = QGraphicsEllipseItem(QRectF(-radius, -radius, radius * 2, radius * 2))
            ring_item.setPen(QPen(QColor(self.pal["line"]), 1, Qt.PenStyle.DashLine))
            ring_item.setZValue(-10)
            self.scene.addItem(ring_item)

        # edges
        for child, parent in parent_of.items():
            if child not in positions or parent not in positions:
                continue
            host = node_host.get(child)
            colour = QColor(self.pal["line"] if host is None else self.pal["accent"])
            colour.setAlpha(150 if host is not None else 90)
            line = self.scene.addLine(positions[parent].x(), positions[parent].y(),
                                      positions[child].x(), positions[child].y(),
                                      QPen(colour, 1.4))
            line.setZValue(-5)

        # nodes
        font = QFont()
        font.setPointSize(8)
        ignore_zoom = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        for name, point in positions.items():
            host = node_host.get(name)
            if name == "localhost":
                kind, radius = "self", 26.0
            elif host is None:
                kind, radius = "hop", 9.0
            else:
                kind = "host"
                radius = 13.0 + min(len(host.open_ports), 24) * 1.1
            node = HostNode(name, host, radius, self.pal, kind)
            node.setPos(point)
            self.scene.addItem(node)

            if self.labels.isChecked() and kind != "hop":
                text = "this machine" if kind == "self" else (
                    host.hostname or name if host else name)
                if kind == "host" and host is not None:
                    # One item, two lines: labels ignore zoom, so separate items
                    # would drift into each other as the view scales.
                    text += f"\n{len(host.open_ports)} open"
                label = QGraphicsSimpleTextItem(text)
                label.setFont(font)
                label.setBrush(QBrush(QColor(self.pal["text"] if kind == "self"
                                             else self.pal["dim"])))
                label.setFlag(ignore_zoom, True)
                label.setPos(point.x(), point.y() + radius + 6)
                label.setZValue(11)
                _centre(label)
                self.scene.addItem(label)

        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60))
        self._user_zoomed = False
        self._fit_soon()

    def _empty(self) -> None:
        text = self.scene.addText("No hosts yet — run a scan to draw the map.")
        text.setDefaultTextColor(QColor(self.pal["faint"]))

    # ------------------------------------------------------------------- ux
    def fit(self) -> None:
        rect = self.scene.itemsBoundingRect()
        if rect.isNull() or self.view.width() < 60 or self.view.height() < 60:
            return
        self.view.fitInView(rect.adjusted(-30, -30, 30, 30),
                            Qt.AspectRatioMode.KeepAspectRatio)
        self._user_zoomed = False

    def _fit_soon(self) -> None:
        """Fit after the layout has settled — fitting too early squashes everything."""
        QTimer.singleShot(0, self.fit)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._user_zoomed:
            self._fit_soon()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._user_zoomed:
            self._fit_soon()

    def zoom(self, factor: float) -> None:
        self.view.scale(factor, factor)
        self._user_zoomed = True

    def _wheel(self, event) -> None:
        self.zoom(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)

    def _mouse_press(self, event) -> None:
        item = self.view.itemAt(event.pos())
        if isinstance(item, HostNode) and item.kind == "host":
            self.host_clicked.emit(item.ip)
        QGraphicsView.mousePressEvent(self.view, event)


def _centre(item: QGraphicsSimpleTextItem) -> None:
    """Shift a zoom-independent label so it sits centred under its node."""
    width = item.boundingRect().width()
    item.setPos(item.pos().x() - width / 2, item.pos().y())
