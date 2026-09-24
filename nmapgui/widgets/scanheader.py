"""The scan header: a progress ring with a live countdown, plus scan controls."""
from __future__ import annotations

import math
import time

from PyQt6.QtCore import (QEasingCurve, QRectF, Qt, QTimer, QVariantAnimation, pyqtSignal)
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from .. import icons
from ..design import DURATION, HIT, RADIUS, SPACE, TYPE
from ..platform_support import can_pause
from ..theme import numeric_font
from .common import Eyebrow, FlowLayout, PulseDot, StatBlock


def fmt_clock(seconds: float | None) -> str:
    """Seconds as M:SS, or H:MM:SS once it runs past an hour."""
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_duration(text: str) -> float | None:
    """nmap hands out '0:00:12' for time remaining; turn that into seconds."""
    if not text:
        return None
    parts = text.strip().split(":")
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    total = 0.0
    for value in values:
        total = total * 60 + value
    return total


class ProgressRing(QWidget):
    """A ring that fills as the scan progresses.

    Three states, each visually distinct: indeterminate (a sweeping arc, for
    before nmap reports a percentage), determinate (a filling arc), and done
    (a closed ring). The value is animated so it never jumps.
    """

    def __init__(self, pal: dict, diameter: int = 132, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setFixedSize(diameter, diameter)
        self._value = 0.0
        self._sweep = 0.0
        self._indeterminate = False
        self._colour = QColor(pal["accent"])
        self._thickness = 7.0

        self._value_anim = QVariantAnimation(self)
        self._value_anim.setDuration(DURATION["slow"])
        self._value_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._value_anim.valueChanged.connect(self._on_value_step)

        self._sweep_anim = QVariantAnimation(self)
        self._sweep_anim.setDuration(DURATION["sweep"])
        self._sweep_anim.setStartValue(0.0)
        self._sweep_anim.setEndValue(360.0)
        self._sweep_anim.setLoopCount(-1)
        self._sweep_anim.valueChanged.connect(self._on_sweep_step)

    # ------------------------------------------------------------------ state
    def set_value(self, fraction: float, animate: bool = True) -> None:
        target = max(0.0, min(1.0, fraction))
        self.set_indeterminate(False)
        if not animate:
            self._value_anim.stop()
            self._value = target
            self.update()
            return
        self._value_anim.stop()
        self._value_anim.setStartValue(self._value)
        self._value_anim.setEndValue(target)
        self._value_anim.start()

    def set_indeterminate(self, on: bool) -> None:
        if on == self._indeterminate:
            return
        self._indeterminate = on
        if on:
            self._sweep_anim.start()
        else:
            self._sweep_anim.stop()
        self.update()

    def set_colour(self, colour: str) -> None:
        self._colour = QColor(colour)
        self.update()

    def stop_animations(self) -> None:
        self._sweep_anim.stop()
        self._value_anim.stop()

    def _on_value_step(self, value) -> None:
        self._value = float(value)
        self.update()

    def _on_sweep_step(self, value) -> None:
        self._sweep = float(value)
        self.update()

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = self._thickness / 2 + 1
        box = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

        track = QPen(QColor(self.pal["line"]), self._thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawEllipse(box)

        arc = QPen(self._colour, self._thickness)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc)
        start = 90 * 16          # twelve o'clock
        if self._indeterminate:
            painter.drawArc(box, int(start - self._sweep * 16), -int(84 * 16))
        elif self._value > 0:
            painter.drawArc(box, start, -int(self._value * 360 * 16))


class ScanHeader(QFrame):
    """Ring + countdown + live metrics + the controls for one scan."""

    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setProperty("role", "card")
        self._state = "idle"
        self._remaining: float | None = None
        self._eta_epoch: float | None = None
        self._elapsed = 0.0
        self._percent = 0.0
        self._last_sync = 0.0

        root = QHBoxLayout(self)
        root.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        root.setSpacing(SPACE["2xl"])

        # ---------------------------------------------------------- the ring
        ring_wrap = self.ring_wrap = QWidget(self)
        ring_wrap.setFixedSize(132, 132)
        ring_wrap.setStyleSheet("background:transparent;")
        self.ring = ProgressRing(pal, 132, ring_wrap)
        self.ring.move(0, 0)

        centre = QWidget(ring_wrap)
        centre.setGeometry(0, 0, 132, 132)
        centre.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        centre.setStyleSheet("background:transparent;")
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(0)
        centre_layout.addStretch(1)

        self.countdown = QLabel("--:--", centre)
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown.setFont(numeric_font(20, 700))
        centre_layout.addWidget(self.countdown)

        self.countdown_caption = QLabel("ready", centre)
        self.countdown_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        centre_layout.addWidget(self.countdown_caption)
        centre_layout.addStretch(1)
        root.addWidget(ring_wrap, 0)

        # --------------------------------------------------------- the detail
        detail = QVBoxLayout()
        detail.setSpacing(SPACE["md"])

        title_row = QHBoxLayout()
        title_row.setSpacing(SPACE["md"])
        self.pulse = PulseDot(pal, pal["accent"], self)
        self.pulse.hide()
        title_row.addWidget(self.pulse, 0, Qt.AlignmentFlag.AlignVCenter)

        self.phase = QLabel("No scan running", self)
        self.phase.setProperty("role", "title")
        title_row.addWidget(self.phase, 1)
        detail.addLayout(title_row)

        self.command = QLabel("", self)
        self.command.setProperty("role", "mono")
        self.command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.command.setMinimumWidth(120)
        self._command_text = ""
        detail.addWidget(self.command)

        # A flow layout so the metrics wrap in a narrow window instead of
        # truncating to "ELAP: / FINIS / HOS1".
        metrics_host = QWidget(self)
        metrics = FlowLayout(metrics_host, SPACE["2xl"])
        self.stat_elapsed = StatBlock("Elapsed", pal, "0:00", parent=metrics_host)
        self.stat_eta = StatBlock("Finishes at", pal, "—", parent=metrics_host)
        self.stat_hosts = StatBlock("Hosts", pal, "—", parent=metrics_host)
        self.stat_ports = StatBlock("Open ports", pal, "—", colour=pal["open"],
                                    parent=metrics_host)
        for block in (self.stat_elapsed, self.stat_eta, self.stat_hosts, self.stat_ports):
            metrics.addWidget(block)
        self.metrics_host = metrics_host
        detail.addWidget(metrics_host)
        root.addLayout(detail, 1)

        # -------------------------------------------------------- the actions
        actions = QVBoxLayout()
        actions.setSpacing(SPACE["md"])
        actions.addStretch(1)

        self.pause_btn = QPushButton("  Pause", self)
        self.pause_btn.setIcon(icons.icon("pause", pal["dim"], 15))
        self.pause_btn.setMinimumHeight(HIT["comfortable"])
        self.pause_btn.setMinimumWidth(104)
        self.pause_btn.setToolTip("Suspend the scan; nmap resumes exactly where it left off")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_requested.emit)
        # Windows has no SIGSTOP, so the button would never do anything there.
        self.pause_btn.setVisible(can_pause())
        actions.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("  Stop", self)
        self.stop_btn.setProperty("danger", "true")
        self.stop_btn.setIcon(icons.icon("stop", pal["closed"], 15))
        self.stop_btn.setMinimumHeight(HIT["comfortable"])
        self.stop_btn.setMinimumWidth(104)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        actions.addWidget(self.stop_btn)
        actions.addStretch(1)
        root.addLayout(actions, 0)

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self.restyle()
        self.show_idle()

    # ------------------------------------------------------------- idle state
    def show_idle(self) -> None:
        """Before anything has run, this is one quiet line — not a card of
        dashes. The ring and the metrics appear when they have something to
        say."""
        self._tick.stop()
        self.pulse.stop()
        self.ring.set_indeterminate(False)
        for widget in (self.ring_wrap, self.metrics_host, self.command,
                       self.pause_btn, self.stop_btn):
            widget.setVisible(False)
        self.phase.setText("Ready — enter a target and press Scan")
        self.phase.setStyleSheet(
            f"color:{self.pal['dim']};font-size:{TYPE['medium']}px;")
        self.layout().setContentsMargins(SPACE["xl"], SPACE["lg"],
                                         SPACE["xl"], SPACE["lg"])

    def show_full(self) -> None:
        for widget in (self.ring_wrap, self.metrics_host, self.command):
            widget.setVisible(True)
        self.pause_btn.setVisible(can_pause())
        self.stop_btn.setVisible(True)
        self.phase.setStyleSheet(
            f"color:{self.pal['text']};font-size:{TYPE['title']}px;font-weight:600;")

    def restyle(self) -> None:
        """Re-apply everything this widget styles itself, after a theme change."""
        pal = self.pal
        self.countdown.setStyleSheet(f"color:{pal['text']};background:transparent;")
        self.countdown_caption.setStyleSheet(
            f"color:{pal['faint']};background:transparent;"
            f"font-size:{TYPE['micro']}px;font-weight:700;")
        self.phase.setStyleSheet(
            f"color:{pal['text']};font-size:{TYPE['title']}px;font-weight:600;")
        self.command.setStyleSheet(f"color:{pal['faint']};")
        self.pause_btn.setIcon(icons.icon(
            "play" if self._state == "paused" else "pause",
            pal["open"] if self._state == "paused" else pal["dim"], 15))
        self.stop_btn.setIcon(icons.icon("stop", pal["closed"], 15))
        self.ring.set_colour({"running": pal["accent"], "paused": pal["filtered"],
                              "stopping": pal["closed"]}.get(self._state, pal["dim"]))

    # ------------------------------------------------------------------- api
    def set_command(self, text: str) -> None:
        """Keep the full command for the tooltip; show as much as fits."""
        self._command_text = text
        self.command.setToolTip(text)
        self._elide_command()

    def _elide_command(self) -> None:
        if not self._command_text:
            self.command.setText("")
            return
        metrics = QFontMetrics(self.command.font())
        self.command.setText(metrics.elidedText(
            self._command_text, Qt.TextElideMode.ElideRight,
            max(self.command.width() - 4, 80)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide_command()

    def reset(self, command: str = "") -> None:
        self.show_full()
        self._remaining = None
        self._eta_epoch = None
        self._elapsed = 0.0
        self._percent = 0.0
        self.set_command(command)
        self.ring.set_value(0.0, animate=False)
        self.countdown.setText("--:--")
        self.countdown_caption.setText("starting")
        self.phase.setText("Starting nmap…")
        for block, value in ((self.stat_elapsed, "0:00"), (self.stat_eta, "—"),
                             (self.stat_hosts, "—"), (self.stat_ports, "—")):
            block.set_value(value)

    def set_state(self, state: str) -> None:
        self._state = state
        running = state in ("running", "paused", "stopping")
        self.stop_btn.setEnabled(running)
        self.pause_btn.setEnabled(can_pause() and state in ("running", "paused"))
        resumable = state == "paused"
        self.pause_btn.setText("  Resume" if resumable else "  Pause")
        self.pause_btn.setIcon(icons.icon("play" if resumable else "pause",
                                          self.pal["open"] if resumable else self.pal["dim"], 15))
        colour = {"running": self.pal["accent"], "paused": self.pal["filtered"],
                  "stopping": self.pal["closed"]}.get(state)
        if colour:
            # Idle keeps whatever the last finish() or show_static() chose, so a
            # completed scan stays green instead of flicking back to blue.
            self.ring.set_colour(colour)
        else:
            colour = self.pal["accent"]

        if state == "running":
            self.pulse.start(colour)
            self._tick.start()
            if self._percent <= 0:
                self.ring.set_indeterminate(True)
                self.countdown_caption.setText("measuring")
        elif state == "paused":
            self.pulse.start(colour)
            self.ring.set_indeterminate(False)
            self.countdown_caption.setText("paused")
        elif state == "stopping":
            self.pulse.start(colour)
            self.countdown_caption.setText("stopping")
        else:
            self.pulse.stop()
            self._tick.stop()
            self.ring.set_indeterminate(False)

    def set_progress(self, progress, elapsed: float) -> None:
        """Fresh numbers from nmap's --stats-every output."""
        self._elapsed = elapsed
        self._last_sync = time.monotonic()
        if progress.task:
            self.phase.setText(progress.task)
        if progress.percent:
            self._percent = progress.percent
            self.ring.set_indeterminate(False)
            self.ring.set_value(progress.percent / 100)
        remaining = parse_duration(progress.remaining)
        if remaining is not None:
            self._remaining = remaining
            self._eta_epoch = time.time() + remaining
        if progress.hosts_done or progress.hosts_up:
            self.stat_hosts.set_value(f"{progress.hosts_done} done · {progress.hosts_up} up")
        self._refresh_countdown()

    def set_result_counts(self, hosts_up: int, hosts_total: int, open_ports: int) -> None:
        self.stat_hosts.set_value(f"{hosts_up} up"
                                  + (f" of {hosts_total}" if hosts_total else ""))
        self.stat_ports.set_value(str(open_ports))

    def finish(self, elapsed: float, ok: bool, note: str) -> None:
        self._tick.stop()
        self.pulse.stop()
        self.ring.set_indeterminate(False)
        self.ring.set_colour(self.pal["open"] if ok else self.pal["closed"])
        self.ring.set_value(1.0 if ok else max(self._percent / 100, 0.02))
        self.countdown.setText(fmt_clock(elapsed))
        self.countdown_caption.setText("total" if ok else "stopped")
        self.phase.setText(note)
        self.stat_elapsed.set_value(fmt_clock(elapsed))
        self.stat_eta.set_value("done" if ok else "—")

    def show_static(self, title: str, command: str, elapsed: float | None = None) -> None:
        """For a scan loaded from history or an XML file — no live timers."""
        self.show_full()
        self._tick.stop()
        self.pulse.stop()
        self.ring.set_indeterminate(False)
        self.ring.set_colour(self.pal["dim"])
        self.ring.set_value(1.0, animate=False)
        self.phase.setText(title)
        self.set_command(command)
        self.countdown.setText(fmt_clock(elapsed) if elapsed else "—")
        self.countdown_caption.setText("total" if elapsed else "loaded")
        self.stat_elapsed.set_value(fmt_clock(elapsed) if elapsed else "—")
        self.stat_eta.set_value("—")
        self.set_state("idle")

    # -------------------------------------------------------------- internals
    def _on_tick(self) -> None:
        """Runs every second so the countdown moves between nmap's updates."""
        if self._state == "paused":
            return
        drift = time.monotonic() - self._last_sync
        self._elapsed += 1
        if self._remaining is not None:
            self._remaining = max(0.0, self._remaining - 1)
        self.stat_elapsed.set_value(fmt_clock(self._elapsed))
        self._refresh_countdown()
        # Creep the ring forward a little between reports so it never looks stuck.
        if self._percent and drift > 2 and self._percent < 99:
            crept = min(0.995, (self._percent + min(drift * 0.08, 1.5)) / 100)
            self.ring.set_value(crept, animate=False)

    def _refresh_countdown(self) -> None:
        if self._state not in ("running", "paused", "stopping"):
            return
        if self._remaining is None:
            self.countdown.setText("--:--")
            if not self.ring._indeterminate and self._percent <= 0:
                self.ring.set_indeterminate(True)
            self.countdown_caption.setText("measuring")
            self.stat_eta.set_value("—")
            return
        self.countdown.setText(fmt_clock(self._remaining))
        # nmap's estimate can run out while a slow phase (version detection,
        # scripts) is still going. Say so rather than sitting on a dead 0:00.
        self.countdown_caption.setText("remaining" if self._remaining >= 1
                                       else "wrapping up")
        if self._eta_epoch:
            self.stat_eta.set_value(time.strftime("%H:%M:%S", time.localtime(self._eta_epoch)))
