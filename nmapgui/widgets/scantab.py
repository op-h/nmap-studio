"""One scan: its process, its live output and every view of its results."""
from __future__ import annotations

import time

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .. import icons
from ..command import ScanConfig
from ..design import SPACE
from ..parser import ScanResult, parse_xml_text
from ..runner import ScanRunner
from .common import fade_in
from .hostsview import HostsView
from .outputview import OutputView
from .portstable import PortsTable
from .scanheader import ScanHeader
from .scriptsview import ScriptsView
from .summaryview import SummaryView
from .topology import TopologyView


class ScanTab(QWidget):
    state_changed = pyqtSignal(str)
    scan_finished = pyqtSignal(object)      # ScanTab
    title_changed = pyqtSignal(str)
    notify = pyqtSignal(str, str)           # message, kind

    def __init__(self, pal: dict, mono_size: int = 10, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.config: ScanConfig | None = None
        self.result: ScanResult | None = None
        self.title = "New scan"
        self.saved_id: int | None = None
        self.started_at = 0.0

        self.runner = ScanRunner(self)
        self.runner.output_chunk.connect(self._on_output)
        self.runner.progress_changed.connect(self._on_progress)
        self.runner.partial_result.connect(self._on_result)
        self.runner.state_changed.connect(self._on_state)
        self.runner.finished.connect(self._on_finished)
        self.runner.failed.connect(self._on_failed)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        root.setSpacing(SPACE["lg"])

        self.header = ScanHeader(pal, self)
        self.header.stop_requested.connect(self.stop)
        self.header.pause_requested.connect(self.toggle_pause)
        root.addWidget(self.header, 0)

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.output = OutputView(pal, mono_size, self)
        self.hosts = HostsView(pal, self)
        self.ports = PortsTable(pal, self)
        self.scripts = ScriptsView(pal, self)
        self.topology = TopologyView(pal, self)
        self.summary = SummaryView(pal, self)
        self.xml_view = OutputView(pal, mono_size, self)

        for widget, name, label in (
                (self.output, "terminal", "Output"),
                (self.hosts, "server", "Hosts"),
                (self.ports, "network", "Ports"),
                (self.scripts, "script", "Scripts"),
                (self.topology, "graph", "Topology"),
                (self.summary, "info", "Summary"),
                (self.xml_view, "code", "XML")):
            self.tabs.addTab(widget, icons.icon(name, pal["dim"], 15), label)
        self.tabs.currentChanged.connect(self._on_view_changed)
        root.addWidget(self.tabs, 1)

        self.topology.host_clicked.connect(self._focus_host)
        self.summary.host_clicked.connect(self._focus_host)
        self._render_summary()

    def restyle(self) -> None:
        for index, name in enumerate(("terminal", "server", "network", "script",
                                      "graph", "info", "code")):
            self.tabs.setTabIcon(index, icons.icon(name, self.pal["dim"], 15))

    # ------------------------------------------------------------------ run
    def start(self, config: ScanConfig, elevate: str = "") -> None:
        self.config = config
        self.result = None
        self.started_at = time.time()
        self.saved_id = None
        self.output.clear()
        self.title = _title_for(config)
        self.title_changed.emit(self.title)
        self.header.reset(config.preview())
        self.runner.start(config, elevate)

    def stop(self) -> None:
        self.runner.stop()

    def toggle_pause(self) -> None:
        if self.runner.state == "paused":
            self.runner.resume()
        else:
            self.runner.pause()

    def is_running(self) -> bool:
        return self.runner.is_running()

    # -------------------------------------------------------------- signals
    def _on_output(self, chunk: str) -> None:
        self.output.append(chunk)

    def _on_progress(self, progress) -> None:
        self.header.set_progress(progress, self.runner.elapsed)

    def _on_result(self, result: ScanResult) -> None:
        self.result = result
        self.hosts.refresh(result)
        self.ports.refresh(result)
        self.scripts.refresh(result)
        self.header.set_result_counts(result.hosts_up, result.hosts_total,
                                      result.open_port_count)
        if not self.runner.is_running():
            self.topology.refresh(result)
        self._render_summary()

    def _on_state(self, state: str) -> None:
        self.header.set_state(state)
        self.state_changed.emit(state)

    def _on_finished(self, code: int, note: str) -> None:
        xml = self.runner.xml_text()
        if xml:
            self.xml_view.set_text(xml)
            parsed = parse_xml_text(xml)
            if parsed is not None:
                self.result = parsed
        if self.result:
            self._on_result(self.result)
        self.topology.refresh(self.result)
        self.output.append(f"\n[nmap-studio] {note}\n")
        self.header.finish(self.runner.elapsed, code == 0, note)
        self._render_summary()
        self.notify.emit(f"{self.title}: {note}", "good" if code == 0 else "warn")
        self.scan_finished.emit(self)

    def _on_failed(self, message: str) -> None:
        self.output.append(f"\n[nmap-studio] {message}\n")
        self.header.phase.setText(message)
        self.notify.emit(message, "bad")

    def _on_view_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is not None:
            fade_in(widget)

    def _focus_host(self, ip: str) -> None:
        self.tabs.setCurrentWidget(self.hosts)
        self.hosts.filter.setText(ip)

    # -------------------------------------------------------------- summary
    def _render_summary(self) -> None:
        self.summary.refresh(self.result)

    # -------------------------------------------------------------- loading
    def load_result(self, xml: str, output: str, title: str, command: str,
                    elapsed: float | None = None) -> None:
        """Populate the tab from a saved scan or an imported XML file."""
        self.title = title
        self.output.set_text(output or "(no console output was stored with this scan)")
        self.xml_view.set_text(xml)
        self.result = parse_xml_text(xml)
        if self.result:
            self._on_result(self.result)
            if elapsed is None and self.result.elapsed:
                try:
                    elapsed = float(self.result.elapsed)
                except ValueError:
                    elapsed = None
        self.topology.refresh(self.result)
        self.header.show_static(title, command, elapsed)
        self.title_changed.emit(title)


def _title_for(config: ScanConfig) -> str:
    targets = config.targets.split()
    if targets:
        head = targets[0]
        extra = f" +{len(targets) - 1}" if len(targets) > 1 else ""
        return f"{head}{extra}"
    return "scan"
