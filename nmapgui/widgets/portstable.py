"""Flat, sortable, filterable table of every port found."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QGuiApplication
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QMenu, QPushButton, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import icons
from ..design import HIT, SPACE
from ..parser import ScanResult
from .common import EmptyState, IconField

COLUMNS = ["Host", "Hostname", "Port", "Proto", "State", "Service", "Version", "Reason", "NSE"]


class _NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            return int(self.text()) < int(other.text())
        except (TypeError, ValueError):
            return super().__lt__(other)


class PortsTable(QWidget):
    port_selected = pyqtSignal(object, object)

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.result: ScanResult | None = None
        self._rows: list[tuple] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, SPACE["md"], 0, 0)
        bar.setSpacing(SPACE["md"])
        self.filter = IconField("filter", pal, self)
        self.filter.setPlaceholderText("Filter — host, port, service, banner…")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)

        self.state_box = QComboBox(self)
        self.state_box.addItems(["open only", "open + filtered", "all states"])
        self.state_box.currentIndexChanged.connect(lambda *_: self.refresh(self.result))
        bar.addWidget(self.state_box)

        copy_btn = QPushButton("  Copy rows", self)
        copy_btn.setIcon(icons.icon("copy", pal["dim"], 15))
        copy_btn.setProperty("flat", "true")
        copy_btn.setMinimumHeight(HIT["min"])
        copy_btn.setToolTip("Copy every visible row as TSV")
        copy_btn.clicked.connect(self.copy_visible)
        bar.addWidget(copy_btn)
        root.addLayout(bar)

        self.stack = QStackedWidget(self)
        self.empty = EmptyState(
            "network", "No ports to show",
            "Every port nmap reports lands in this table — sort it, filter it, or copy "
            "the visible rows straight into your notes.", pal, self)
        self.stack.addWidget(self.empty)
        self.table = QTableWidget(self)
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemSelectionChanged.connect(self._on_selection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.stack.addWidget(self.table)
        root.addWidget(self.stack, 1)

        self.summary = QLabel("", self)
        self.summary.setProperty("role", "dim")
        self.summary.setContentsMargins(SPACE["xs"], 0, SPACE["xs"], 0)
        root.addWidget(self.summary)

    def restyle(self) -> None:
        self.refresh(self.result)

    # ------------------------------------------------------------------ data
    def refresh(self, result: ScanResult | None) -> None:
        self.result = result
        wanted = {0: {"open"}, 1: {"open", "filtered", "open|filtered"}}.get(
            self.state_box.currentIndex())

        self._rows = []
        if result is not None:
            for host in result.hosts:
                for port in host.ports:
                    if wanted is not None and port.state not in wanted:
                        continue
                    self._rows.append((host, port))

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))
        for row, (host, port) in enumerate(self._rows):
            svc = port.service
            values = [host.ip, host.hostname, str(port.portid), port.protocol, port.state,
                      svc.name, svc.banner, port.reason,
                      ", ".join(port.scripts) if port.scripts else ""]
            for col, value in enumerate(values):
                item = _NumericItem(value) if col == 2 else QTableWidgetItem(value)
                if col == 4:
                    colour = {"open": self.pal["open"], "closed": self.pal["closed"]}.get(
                        port.state, self.pal["filtered"])
                    item.setForeground(QBrush(QColor(colour)))
                if col == 8 and port.scripts:
                    item.setToolTip("\n\n".join(f"{k}:\n{v}" for k, v in port.scripts.items()))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(6, max(220, self.table.columnWidth(6)))
        self._apply_filter(self.filter.text())
        self.stack.setCurrentIndex(1 if self._rows else 0)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        visible = 0
        for row in range(self.table.rowCount()):
            hay = " ".join(self.table.item(row, c).text().lower()
                           for c in range(self.table.columnCount())
                           if self.table.item(row, c))
            show = not needle or needle in hay
            self.table.setRowHidden(row, not show)
            visible += int(show)
        hosts = len({h.ip for h, _ in self._rows})
        self.summary.setText(f"{visible} of {len(self._rows)} ports shown across {hosts} hosts")

    # --------------------------------------------------------------- actions
    def _on_selection(self) -> None:
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) == 1:
            row = rows.pop()
            key = (self.table.item(row, 0).text(), self.table.item(row, 2).text(),
                   self.table.item(row, 3).text())
            for host, port in self._rows:
                if (host.ip, str(port.portid), port.protocol) == key:
                    self.port_selected.emit(host, port)
                    break

    def copy_visible(self) -> None:
        lines = ["\t".join(COLUMNS)]
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            lines.append("\t".join(
                self.table.item(row, c).text() if self.table.item(row, c) else ""
                for c in range(self.table.columnCount())))
        QGuiApplication.clipboard().setText("\n".join(lines))

    def _context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        host_ip = self.table.item(row, 0).text()
        port = self.table.item(row, 2).text()
        menu = QMenu(self)
        menu.addAction(icons.icon("copy", self.pal["dim"], 15), "Copy cell",
                       lambda: QGuiApplication.clipboard().setText(item.text()))
        menu.addAction("Copy host", lambda: QGuiApplication.clipboard().setText(host_ip))
        menu.addAction("Copy host:port",
                       lambda: QGuiApplication.clipboard().setText(f"{host_ip}:{port}"))
        menu.addSeparator()
        menu.addAction("Copy all visible rows (TSV)", self.copy_visible)
        menu.addAction("Filter on this value", lambda: self.filter.setText(item.text()))
        menu.exec(self.table.viewport().mapToGlobal(pos))
