"""Runs nmap and turns its output into live signals.

The process runs on a pseudo-terminal: nmap block-buffers stdout when it is not
a terminal, which would delay every `--stats-every` line to the end of the scan
and leave the progress ring and countdown with nothing to show.
"""
from __future__ import annotations

import os
import signal
import tempfile
import time

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

from .command import NMAP, ScanConfig, elevated_argv, is_root, nmap_available
from .parser import (Progress, ScanResult, parse_xml_text, progress_from_xml,
                     scrape_progress)
from .platform_support import can_pause, no_window_flags
from .process import HAVE_PTY, PtyProcess, WinPtyProcess, have_winpty


class ScanRunner(QObject):
    """One nmap invocation. Reusable: call start() again after it finishes."""

    output_chunk = pyqtSignal(str)          # raw text as it arrives
    progress_changed = pyqtSignal(object)   # Progress
    partial_result = pyqtSignal(object)     # ScanResult, refreshed while running
    state_changed = pyqtSignal(str)         # idle | running | paused | stopping
    finished = pyqtSignal(int, str)         # exit code, summary line
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.using_pty = False
        self._saw_stdout_progress = False
        self.config: ScanConfig | None = None
        self.argv: list[str] = []
        self.xml_path = ""
        self.output = ""
        self.progress = Progress()
        self.result: ScanResult | None = None
        self.started_at = 0.0
        self.finished_at = 0.0
        self.state = "idle"
        self._xml_size = -1
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._poll_xml)

    # ------------------------------------------------------------------ run
    def start(self, config: ScanConfig, elevate: str = "") -> None:
        if self.is_running():
            self.failed.emit("A scan is already running in this tab.")
            return
        if not nmap_available():
            self.failed.emit(
                f"nmap was not found (looked for {NMAP}). Install it and, on "
                "Windows, make sure the Nmap folder is on PATH.")
            return

        self.config = config
        self.output = ""
        self.result = None
        self.progress = Progress()
        self._saw_stdout_progress = False
        self._xml_size = -1
        fd, self.xml_path = tempfile.mkstemp(prefix="nmapgui-", suffix=".xml")
        os.close(fd)

        argv = config.argv(self.xml_path)
        if elevate and not is_root():
            argv = elevated_argv(argv, elevate)
        self.argv = argv

        self.started_at = time.time()
        self.finished_at = 0.0
        self._set_state("running")
        self.output_chunk.emit("$ " + " ".join(argv) + "\n\n")

        if HAVE_PTY or have_winpty():
            self.using_pty = True
            proc = PtyProcess(self) if HAVE_PTY else WinPtyProcess(self)
            proc.output.connect(self._ingest)
            proc.finished.connect(self._on_finished)
            proc.failed.connect(self._on_pty_failure)
            self.proc = proc
            if not proc.start(argv):
                return
        else:
            self.using_pty = False
            proc = QProcess(self)
            proc.setProgram(argv[0])
            proc.setArguments(argv[1:])
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            proc.readyReadStandardOutput.connect(self._read_qprocess)
            proc.finished.connect(lambda code, _status: self._on_finished(code))
            proc.errorOccurred.connect(self._on_qprocess_error)
            flags = no_window_flags()
            if flags and hasattr(proc, "setCreateProcessArgumentsModifier"):
                # Keep Windows from flashing a console window for every scan.
                proc.setCreateProcessArgumentsModifier(
                    lambda args: setattr(args, "flags", args.flags | flags))
            self.proc = proc
            proc.start()

        self._poll.start()

    # --------------------------------------------------------------- control
    def is_running(self) -> bool:
        if self.proc is None:
            return False
        if isinstance(self.proc, QProcess):
            return self.proc.state() != QProcess.ProcessState.NotRunning
        return self.proc.is_running()

    def stop(self) -> None:
        if not self.is_running():
            return
        self._set_state("stopping")
        self.output_chunk.emit("\n[nmap-studio] stopping scan…\n")
        cont = getattr(signal, "SIGCONT", None)     # POSIX only
        if cont and self.state == "paused" and hasattr(self.proc, "send_signal"):
            self.proc.send_signal(cont)             # a stopped process cannot exit
        self.proc.terminate()
        QTimer.singleShot(4000, self._force_kill)

    def _force_kill(self) -> None:
        if self.is_running():
            self.output_chunk.emit("[nmap-studio] process did not exit, killing it.\n")
            self.proc.kill()

    def pause(self) -> None:
        """SIGSTOP the scan. nmap picks up where it left off on resume."""
        if not (self.is_running() and self.state == "running"):
            return
        stop_signal = getattr(signal, "SIGSTOP", None)
        if not can_pause() or stop_signal is None:
            self.failed.emit("Pausing a scan is not supported on this platform.")
            return
        if self._signal(stop_signal):
            self._set_state("paused")
            self.output_chunk.emit("\n[nmap-studio] paused\n")
        else:
            self.failed.emit(
                "Could not pause — the scan is running with elevated privileges, "
                "so it cannot be signalled from here.")

    def resume(self) -> None:
        if not (self.is_running() and self.state == "paused"):
            return
        if self._signal(getattr(signal, "SIGCONT", 0)):
            self._set_state("running")
            self.output_chunk.emit("[nmap-studio] resumed\n")
        else:
            self.failed.emit("Could not resume the scan.")

    def _signal(self, sig: int) -> bool:
        if hasattr(self.proc, "send_signal"):
            return self.proc.send_signal(sig)
        try:
            os.kill(int(self.proc.processId()), sig)
            return True
        except (ProcessLookupError, PermissionError, OSError, ValueError):
            return False

    def send_key(self, key: str) -> None:
        """nmap's runtime keys: v/V verbosity, d/D debug, p/P packet trace, Enter status."""
        if not self.is_running():
            return
        self.proc.write(key.encode())

    # ----------------------------------------------------------------- input
    def _read_qprocess(self) -> None:
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self._ingest(data)

    def _ingest(self, data: str) -> None:
        self.output += data
        self.output_chunk.emit(data)
        prog = scrape_progress(data, self.progress)
        if prog is not None:
            self._saw_stdout_progress = True
            self.progress = prog
            self.progress_changed.emit(prog)

    def _poll_xml(self) -> None:
        """Re-parse the XML nmap is streaming out, but only when it grew."""
        if not self.xml_path or not os.path.exists(self.xml_path):
            return
        try:
            size = os.path.getsize(self.xml_path)
            if size == self._xml_size:
                return
            self._xml_size = size
            with open(self.xml_path, "r", errors="replace") as fh:
                text = fh.read()
        except OSError:
            return
        result = parse_xml_text(text)
        if result is None:
            return
        self.result = result
        self.partial_result.emit(result)
        # Without a terminal nmap prints no estimates, but it still records them
        # in the XML, so fall back to those rather than showing nothing.
        if not self._saw_stdout_progress:
            prog = progress_from_xml(result, self.progress)
            if prog is not None:
                self.progress = prog
                self.progress_changed.emit(prog)

    # -------------------------------------------------------------- lifecycle
    def _on_pty_failure(self, message: str) -> None:
        self._poll.stop()
        self._set_state("idle")
        self.failed.emit(message)

    def _on_qprocess_error(self, err) -> None:
        names = {
            QProcess.ProcessError.FailedToStart:
                "nmap failed to start. Check that it is installed and on $PATH.",
            QProcess.ProcessError.Crashed: "nmap crashed or was killed.",
            QProcess.ProcessError.Timedout: "nmap timed out.",
            QProcess.ProcessError.WriteError: "Could not write to the nmap process.",
            QProcess.ProcessError.ReadError: "Could not read from the nmap process.",
        }
        if err == QProcess.ProcessError.Crashed and self.state == "stopping":
            return
        self.failed.emit(names.get(err, "Unknown process error."))

    def _on_finished(self, code: int) -> None:
        was_stopping = self.state == "stopping"
        self._poll.stop()
        self.finished_at = time.time()
        self._poll_xml()
        if self.result is None and self.xml_path and os.path.exists(self.xml_path):
            try:
                with open(self.xml_path, errors="replace") as fh:
                    self.result = parse_xml_text(fh.read())
            except OSError:
                pass
        self._set_state("idle")

        if was_stopping or code in (15, -15, -9, 143):
            note = "Scan stopped."
        elif code == 0:
            note = (self.result.summary if self.result and self.result.summary
                    else "Scan finished.")
        elif code == 126 or code == 127:
            note = "Could not launch nmap (or the elevation prompt was dismissed)."
        else:
            note = f"nmap exited with code {code}."
        self.finished.emit(code, note)

    def cleanup(self) -> None:
        if self.xml_path and os.path.exists(self.xml_path):
            try:
                os.unlink(self.xml_path)
            except OSError:
                pass
        self.xml_path = ""

    def xml_text(self) -> str:
        if self.xml_path and os.path.exists(self.xml_path):
            try:
                with open(self.xml_path, errors="replace") as fh:
                    return fh.read()
            except OSError:
                return ""
        return ""

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.finished_at if self.finished_at > self.started_at else time.time()
        return end - self.started_at

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)
