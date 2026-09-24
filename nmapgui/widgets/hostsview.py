"""Host tree with a rich detail panel."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QHeaderView, QLineEdit, QSplitter,
                             QStackedWidget, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from .. import icons
from ..design import SPACE
from ..parser import Host, ScanResult
from .common import EmptyState, IconField

STATE_ROLE = Qt.ItemDataRole.UserRole + 1
HOST_ROLE = Qt.ItemDataRole.UserRole + 2


class HostsView(QWidget):
    host_selected = pyqtSignal(object)
    port_activated = pyqtSignal(object, object)

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
        self.filter.setPlaceholderText("Filter hosts, ports, services…")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)
        self.open_only = QCheckBox("Open ports only", self)
        self.open_only.setChecked(True)
        self.open_only.toggled.connect(lambda *_: self.refresh(self.result))
        bar.addWidget(self.open_only)
        self.up_only = QCheckBox("Live hosts only", self)
        self.up_only.setChecked(True)
        self.up_only.toggled.connect(lambda *_: self.refresh(self.result))
        bar.addWidget(self.up_only)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Vertical, self)
        self.stack = QStackedWidget(self)
        self.empty = EmptyState(
            "server", "No hosts yet",
            "Hosts appear here as soon as nmap finishes with them — you do not have to "
            "wait for the whole scan.", pal, self)
        self.stack.addWidget(self.empty)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Host / Port", "State", "Service", "Version", "Reason"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.currentItemChanged.connect(self._on_current)
        self.tree.itemDoubleClicked.connect(self._on_double)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 130)
        self.stack.addWidget(self.tree)
        split.addWidget(self.stack)

        self.detail = QTextBrowser(self)
        self.detail.setOpenExternalLinks(True)
        split.addWidget(self.detail)
        split.setSizes([420, 260])
        root.addWidget(split, 1)
        self._placeholder()

    def restyle(self) -> None:
        self.refresh(self.result)
        if self.tree.currentItem() is None:
            self._placeholder()

    # ------------------------------------------------------------------ data
    def refresh(self, result: ScanResult | None) -> None:
        self.result = result
        current_ip = None
        item = self.tree.currentItem()
        if item is not None:
            host = item.data(0, HOST_ROLE)
            current_ip = host.ip if isinstance(host, Host) else None

        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        if result is not None:
            for host in result.hosts:
                if self.up_only.isChecked() and host.state != "up":
                    continue
                node = self._host_item(host)
                self.tree.addTopLevelItem(node)
                # Expansion only sticks once the item is in the tree.
                node.setExpanded(node.childCount() <= 25)
        self.tree.setUpdatesEnabled(True)
        self._apply_filter(self.filter.text())
        self.stack.setCurrentIndex(1 if self.tree.topLevelItemCount() else 0)

        if current_ip:
            for i in range(self.tree.topLevelItemCount()):
                node = self.tree.topLevelItem(i)
                host = node.data(0, HOST_ROLE)
                if isinstance(host, Host) and host.ip == current_ip:
                    self.tree.setCurrentItem(node)
                    break

    def _host_item(self, host: Host) -> QTreeWidgetItem:
        pal = self.pal
        ports = host.open_ports if self.open_only.isChecked() else host.ports
        label = host.display
        node = QTreeWidgetItem([label, host.state, f"{len(host.open_ports)} open",
                                host.best_os, host.reason])
        node.setData(0, HOST_ROLE, host)
        colour = pal["open"] if host.state == "up" else pal["faint"]
        node.setIcon(0, icons.icon("server", colour, 16))
        node.setForeground(1, QBrush(QColor(colour)))
        font = node.font(0)
        font.setBold(True)
        node.setFont(0, font)
        if host.best_os:
            node.setToolTip(3, "\n".join(f"{m.accuracy}%  {m.name}" for m in host.osmatches[:6]))

        for port in ports:
            state_colour = {"open": pal["open"], "closed": pal["closed"]}.get(
                port.state, pal["filtered"])
            child = QTreeWidgetItem([port.label, port.state, port.service.name,
                                     port.service.banner, port.reason])
            child.setData(0, HOST_ROLE, host)
            child.setData(0, STATE_ROLE, port)
            child.setIcon(0, icons.icon("dot", state_colour, 11))
            child.setForeground(1, QBrush(QColor(state_colour)))
            if port.scripts:
                child.setIcon(2, icons.icon("script", pal["purple"], 13))
                child.setToolTip(2, "\n\n".join(f"{k}:\n{v}" for k, v in port.scripts.items()))
            node.addChild(child)
        return node

    # --------------------------------------------------------------- filter
    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            host_match = not needle or needle in _row_text(node)
            visible_children = 0
            for j in range(node.childCount()):
                child = node.child(j)
                show = host_match or needle in _row_text(child)
                child.setHidden(not show)
                visible_children += int(show)
            node.setHidden(not (host_match or visible_children))
            if needle and visible_children:
                node.setExpanded(True)

    # -------------------------------------------------------------- details
    def _on_current(self, item: QTreeWidgetItem | None, _prev=None) -> None:
        if item is None:
            self._placeholder()
            return
        host = item.data(0, HOST_ROLE)
        port = item.data(0, STATE_ROLE)
        if isinstance(host, Host):
            self.detail.setHtml(self._host_html(host, port))
            self.host_selected.emit(host)

    def _on_double(self, item: QTreeWidgetItem, _col: int) -> None:
        host, port = item.data(0, HOST_ROLE), item.data(0, STATE_ROLE)
        if host is not None and port is not None:
            self.port_activated.emit(host, port)

    def _placeholder(self) -> None:
        pal = self.pal
        self.detail.setHtml(
            f'<div style="color:{pal["faint"]};font-family:sans-serif;padding:18px;">'
            "Select a host to see its addresses, OS fingerprint, script output and "
            "traceroute.</div>")

    def _host_html(self, host: Host, port=None) -> str:
        pal = self.pal
        def row(key, value):
            return (f'<tr><td style="color:{pal["dim"]};padding:2px 14px 2px 0;'
                    f'white-space:nowrap;">{key}</td>'
                    f'<td style="color:{pal["text"]};">{value}</td></tr>')

        parts = [f'<div style="font-family:sans-serif;color:{pal["text"]};padding:4px 8px;">']
        parts.append(f'<h3 style="margin:0 0 8px;">{host.display}</h3><table>')
        parts.append(row("State", f'<span style="color:'
                                  f'{pal["open"] if host.state == "up" else pal["closed"]}">'
                                  f'{host.state}</span> ({host.reason})'))
        for addr, kind, vendor in host.addresses:
            parts.append(row(kind.upper(), addr + (f" — {vendor}" if vendor else "")))
        if len(host.hostnames) > 1:
            parts.append(row("Hostnames", ", ".join(n for n, _ in host.hostnames)))
        counts = {}
        for p in host.ports:
            counts[p.state] = counts.get(p.state, 0) + 1
        if counts:
            parts.append(row("Ports", " · ".join(f"{v} {k}" for k, v in sorted(counts.items()))))
        for state, count, reasons in host.extraports:
            parts.append(row("Not shown", f"{count} {state} ports — {reasons}"))
        if host.distance:
            parts.append(row("Distance", f"{host.distance} hops"))
        if host.uptime:
            days = int(host.uptime) / 86400
            parts.append(row("Uptime", f"{days:.1f} days (last boot {host.lastboot})"))
        if host.tcpsequence:
            parts.append(row("TCP sequence", host.tcpsequence))
        if host.ipidsequence:
            parts.append(row("IP ID sequence", host.ipidsequence))
        parts.append("</table>")

        if host.osmatches:
            parts.append(f'<h4 style="margin:14px 0 4px;">OS fingerprint</h4><table>')
            for match in host.osmatches[:6]:
                bar_w = max(6, int(match.accuracy * 0.9))
                parts.append(
                    f'<tr><td style="padding-right:10px;color:{pal["text"]};">{match.name}</td>'
                    f'<td style="color:{pal["dim"]};white-space:nowrap;">'
                    f'<span style="background:{pal["accent"]};color:{pal["accent"]};">'
                    f'{"&nbsp;" * (bar_w // 8)}</span> {match.accuracy}%</td></tr>')
                if match.osclass:
                    parts.append(f'<tr><td colspan="2" style="color:{pal["faint"]};'
                                 f'font-size:11px;padding-bottom:6px;">{match.osclass}</td></tr>')
            parts.append("</table>")

        if port is not None:
            parts.append(f'<h4 style="margin:14px 0 4px;">Port {port.label}</h4><table>')
            svc = port.service
            parts.append(row("State", f'{port.state} ({port.reason}, ttl {port.reason_ttl})'))
            if svc.name:
                parts.append(row("Service", svc.name))
            if svc.banner:
                parts.append(row("Version", svc.banner))
            if svc.ostype:
                parts.append(row("OS type", svc.ostype))
            if svc.method:
                parts.append(row("Detected by", f"{svc.method} (confidence {svc.conf}/10)"))
            for cpe in svc.cpes:
                parts.append(row("CPE", f'<code style="color:{pal["cyan"]}">{cpe}</code>'))
            parts.append("</table>")
            for sid, output in port.scripts.items():
                parts.append(_script_html(sid, output, pal))

        if host.hostscripts:
            parts.append('<h4 style="margin:14px 0 4px;">Host scripts</h4>')
            for sid, output in host.hostscripts.items():
                parts.append(_script_html(sid, output, pal))

        if host.trace:
            parts.append('<h4 style="margin:14px 0 4px;">Traceroute</h4><table>')
            for hop in host.trace:
                parts.append(f'<tr><td style="color:{pal["dim"]};padding-right:12px;">'
                             f'{hop.ttl}</td><td><code>{hop.ipaddr}</code> '
                             f'{hop.host}</td><td style="color:{pal["dim"]};">'
                             f'{hop.rtt} ms</td></tr>')
            parts.append("</table>")
        parts.append("</div>")
        return "".join(parts)


def _script_html(sid: str, output: str, pal: dict) -> str:
    safe = (output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    colour = pal["closed"] if "VULNERABLE" in output else pal["purple"]
    return (f'<div style="margin:8px 0;"><b style="color:{colour};">{sid}</b></div>'
            + code_block(safe, pal))


def code_block(safe_text: str, pal: dict) -> str:
    """Qt's rich text ignores padding on <pre>, so pad with a table cell instead."""
    return (f'<table width="100%" cellpadding="8" cellspacing="0" border="0" '
            f'bgcolor="{pal["term_bg"]}"><tr><td>'
            f'<pre style="color:{pal["dim"]};white-space:pre-wrap;margin:0;">{safe_text}</pre>'
            "</td></tr></table>")


def _row_text(item: QTreeWidgetItem) -> str:
    return " ".join(item.text(i) for i in range(item.columnCount())).lower()
