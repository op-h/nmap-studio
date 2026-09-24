"""Scan summary: stat cards, service breakdown and findings, as real widgets."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

from ..design import RADIUS, SPACE, TYPE
from ..parser import ScanResult
from ..theme import numeric_font
from .common import AnimatedNumber, Card, EmptyState, Eyebrow, FlowLayout


class StatCard(QFrame):
    def __init__(self, label: str, pal: dict, colour: str, parent=None):
        super().__init__(parent)
        self.setProperty("role", "panel")
        self.setMinimumWidth(124)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        layout.setSpacing(SPACE["xs"])
        layout.addWidget(Eyebrow(label, pal, self))
        self.number = AnimatedNumber(pal, TYPE["display"], colour, self)
        layout.addWidget(self.number)


class Bar(QFrame):
    """Label, proportional bar, count. Clickable when it stands for a host."""

    clicked = pyqtSignal(str)

    def __init__(self, name: str, count: int, biggest: int, pal: dict, colour: str,
                 payload: str = "", parent=None):
        super().__init__(parent)
        self.payload = payload
        self.pal = pal
        self.setProperty("role", "")
        self.setStyleSheet(
            f"QFrame:hover {{ background: {pal['surface2']}; border-radius: "
            f"{RADIUS['chip']}px; }}")
        if payload:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.setToolTip(f"Show {payload} in the Hosts view")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["sm"], 2, SPACE["sm"], 2)
        layout.setSpacing(SPACE["lg"])

        label = QLabel(name, self)
        label.setMinimumWidth(190)
        label.setMaximumWidth(190)
        label.setToolTip(name)
        layout.addWidget(label)

        track = QFrame(self)
        track.setFixedHeight(8)
        track.setStyleSheet(f"background:{pal['line']};border-radius:4px;")
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        fill = QFrame(track)
        fill.setFixedHeight(8)
        fill.setStyleSheet(f"background:{colour};border-radius:4px;")
        fill.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ratio = count / biggest if biggest else 0
        track_layout.addWidget(fill, max(int(ratio * 1000), 8))
        track_layout.addStretch(max(int((1 - ratio) * 1000), 0))
        layout.addWidget(track, 1)

        value = QLabel(str(count), self)
        value.setFont(numeric_font(TYPE["body"] * 0.78, 600))
        value.setStyleSheet(f"color:{pal['dim']};")
        value.setFixedWidth(44)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value)

    def mouseReleaseEvent(self, event):
        if self.payload and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.payload)
        super().mouseReleaseEvent(event)


class SummaryView(QScrollArea):
    host_clicked = pyqtSignal(str)

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setWidgetResizable(True)
        self._body = QWidget()
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(0, 0, SPACE["md"], 0)
        self._layout.setSpacing(SPACE["lg"])
        self.setWidget(self._body)
        self._result: ScanResult | None = None
        self.refresh(None)

    # ------------------------------------------------------------------ build
    def refresh(self, result: ScanResult | None) -> None:
        self._result = result
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        pal = self.pal
        if result is None:
            self._layout.addWidget(EmptyState(
                "info", "No results yet",
                "Run a scan and this page summarises it: hosts that answered, the "
                "services behind each open port, software versions, OS guesses and "
                "anything the scripts flagged.", pal, self._body))
            return

        services: dict[str, int] = {}
        products: dict[str, int] = {}
        flagged: list[tuple[str, str]] = []
        for host in result.hosts:
            for port in host.open_ports:
                name = port.service.name or "unknown"
                services[name] = services.get(name, 0) + 1
                if port.service.product:
                    key = f"{port.service.product} {port.service.version}".strip()
                    products[key] = products.get(key, 0) + 1
            groups = [("host", host.hostscripts)] + [(p.label, p.scripts) for p in host.ports]
            for where, scripts in groups:
                for sid, output in scripts.items():
                    if "VULNERABLE" in output and "NOT VULNERABLE" not in output:
                        flagged.append((host.ip, f"{where} · {sid}"))

        cards = QWidget(self._body)
        cards_layout = FlowLayout(cards, SPACE["lg"])
        for label, value, colour, suffix in (
                ("Hosts up", result.hosts_up, pal["open"], ""),
                ("Scanned", result.hosts_total, pal["text"], ""),
                ("Open ports", result.open_port_count, pal["accent"], ""),
                ("Services", len(services), pal["text"], ""),
                ("Elapsed", _seconds(result.elapsed), pal["text"], "s"),
                ("Flagged", len(flagged), pal["closed"] if flagged else pal["dim"], "")):
            card = StatCard(label, pal, colour, cards)
            card.number.set_value(value, suffix)
            cards_layout.addWidget(card)
        self._layout.addWidget(cards)

        meta = Card(pal, self._body, padding=SPACE["lg"], panel=True)
        meta.body().setSpacing(SPACE["xs"])
        command = QLabel(result.args, meta)
        command.setWordWrap(True)
        command.setProperty("role", "mono")
        command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        command.setStyleSheet(f"color:{pal['dim']};")
        meta.body().addWidget(command)
        if result.summary:
            done = QLabel(result.summary, meta)
            done.setWordWrap(True)
            done.setStyleSheet(f"color:{pal['faint']};font-size:{TYPE['small']}px;")
            meta.body().addWidget(done)
        self._layout.addWidget(meta)

        if flagged:
            box = self._section("Scripts reporting VULNERABLE", pal["closed"])
            for ip, what in flagged[:60]:
                row = QLabel(f"{ip}   {what}", box)
                row.setStyleSheet(f"color:{pal['closed']};font-size:{TYPE['body']}px;")
                box.body().addWidget(row)

        if services:
            box = self._section("Services seen")
            biggest = max(services.values())
            for name, count in sorted(services.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
                box.body().addWidget(Bar(name, count, biggest, pal, pal["accent"], parent=box))

        if products:
            box = self._section("Software identified")
            biggest = max(products.values())
            for name, count in sorted(products.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
                box.body().addWidget(Bar(name, count, biggest, pal, pal["purple"], parent=box))

        os_rows = [(h.ip, h.best_os, h.os_accuracy) for h in result.hosts if h.best_os]
        if os_rows:
            box = self._section("Operating systems")
            grid = QWidget(box)
            grid_layout = QGridLayout(grid)
            grid_layout.setContentsMargins(SPACE["sm"], 0, 0, 0)
            grid_layout.setHorizontalSpacing(SPACE["xl"])
            grid_layout.setVerticalSpacing(SPACE["xs"])
            for row, (ip, name, accuracy) in enumerate(os_rows[:30]):
                address = QLabel(ip, grid)
                address.setProperty("role", "mono")
                address.setStyleSheet(f"color:{pal['accent']};")
                grid_layout.addWidget(address, row, 0)
                grid_layout.addWidget(QLabel(name, grid), row, 1)
                conf = QLabel(f"{accuracy}%", grid)
                conf.setFont(numeric_font(TYPE["body"] * 0.78, 500))
                conf.setStyleSheet(f"color:{pal['faint']};")
                grid_layout.addWidget(conf, row, 2)
            grid_layout.setColumnStretch(1, 1)
            box.body().addWidget(grid)

        busiest = [h for h in sorted(result.hosts, key=lambda h: -len(h.open_ports))
                   if h.open_ports][:15]
        if len(busiest) > 1:
            box = self._section("Busiest hosts")
            biggest = len(busiest[0].open_ports)
            for host in busiest:
                bar = Bar(host.display, len(host.open_ports), biggest, pal, pal["open"],
                          payload=host.ip, parent=box)
                bar.clicked.connect(self.host_clicked.emit)
                box.body().addWidget(bar)

        self._layout.addStretch(1)

    def restyle(self) -> None:
        self.refresh(self._result)

    def _section(self, title: str, colour: str | None = None) -> Card:
        card = Card(self.pal, self._body, padding=SPACE["lg"])
        card.body().setSpacing(SPACE["sm"])
        header = QLabel(title, card)
        header.setStyleSheet(
            f"color:{colour or self.pal['text']};font-size:{TYPE['medium']}px;font-weight:600;")
        card.body().addWidget(header)
        self._layout.addWidget(card)
        return card


def _seconds(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
