"""All NSE output from a scan, grouped by host and script."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QSplitter, QStackedWidget,
                             QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import icons
from ..design import SPACE
from ..parser import ScanResult
from .common import EmptyState, IconField
from .hostsview import code_block

OUTPUT_ROLE = Qt.ItemDataRole.UserRole + 1


class ScriptsView(QWidget):
    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.result: ScanResult | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, SPACE["md"], 0, 0)
        bar.setSpacing(SPACE["md"])
        self.filter = IconField("search", pal, self)
        self.filter.setPlaceholderText("Filter script output — try VULNERABLE, CVE")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)
        self.count = QLabel("", self)
        self.count.setProperty("role", "dim")
        bar.addWidget(self.count)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        self.stack = QStackedWidget(self)
        self.empty = EmptyState(
            "script", "No script output",
            "Pick NSE scripts in the builder — or run -sC — and their findings appear "
            "here, grouped by host, with anything reporting VULNERABLE called out.",
            pal, self)
        self.stack.addWidget(self.empty)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Host / script", "Where"])
        self.tree.setColumnWidth(0, 280)
        self.tree.currentItemChanged.connect(self._show)
        self.stack.addWidget(self.tree)
        split.addWidget(self.stack)

        self.view = QTextBrowser(self)
        split.addWidget(self.view)
        split.setSizes([360, 560])
        root.addWidget(split, 1)

    def restyle(self) -> None:
        current = self.tree.currentItem()
        self.refresh(self.result)
        self._show(current)

    def refresh(self, result: ScanResult | None) -> None:
        self.result = result
        self.tree.clear()
        total = 0
        if result is None:
            self.count.setText("")
            self.stack.setCurrentIndex(0)
            return
        for host in result.hosts:
            entries = [("host", sid, out) for sid, out in host.hostscripts.items()]
            for port in host.ports:
                entries += [(port.label, sid, out) for sid, out in port.scripts.items()]
            if not entries:
                continue
            node = QTreeWidgetItem([host.display, f"{len(entries)} results"])
            node.setIcon(0, icons.icon("server", self.pal["accent"], 15))
            for where, sid, output in entries:
                vulnerable = "VULNERABLE" in output or "CVE-" in output
                child = QTreeWidgetItem([sid, where])
                child.setData(0, OUTPUT_ROLE, (host.display, where, sid, output))
                child.setIcon(0, icons.icon(
                    "warning" if vulnerable else "script",
                    self.pal["closed"] if vulnerable else self.pal["purple"], 14))
                if vulnerable:
                    child.setForeground(0, QBrush(QColor(self.pal["closed"])))
                node.addChild(child)
                total += 1
            node.setExpanded(True)
            self.tree.addTopLevelItem(node)
        self.count.setText(f"{total} script result{'' if total == 1 else 's'}")
        self._apply_filter(self.filter.text())
        self.stack.setCurrentIndex(1 if total else 0)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            shown = 0
            for j in range(node.childCount()):
                child = node.child(j)
                data = child.data(0, OUTPUT_ROLE) or ("", "", "", "")
                hay = f"{data[2]} {data[3]} {node.text(0)}".lower()
                show = not needle or needle in hay
                child.setHidden(not show)
                shown += int(show)
            node.setHidden(shown == 0)

    def _show(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        pal = self.pal
        if item is None or item.data(0, OUTPUT_ROLE) is None:
            self.view.setHtml(f'<div style="color:{pal["faint"]};padding:16px;'
                              'font-family:sans-serif;">Select a script result.</div>')
            return
        host, where, sid, output = item.data(0, OUTPUT_ROLE)
        safe = output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for token, colour in (("VULNERABLE", pal["closed"]), ("LIKELY VULNERABLE", pal["closed"]),
                              ("NOT VULNERABLE", pal["open"])):
            safe = safe.replace(token, f'<b style="color:{colour}">{token}</b>')
        self.view.setHtml(
            f'<div style="font-family:sans-serif;color:{pal["text"]};padding:6px 10px;">'
            f'<h3 style="margin:0 0 2px;">{sid}</h3>'
            f'<div style="color:{pal["dim"]};margin-bottom:10px;">{host} · {where}</div>'
            + code_block(safe, pal) + "</div>")
