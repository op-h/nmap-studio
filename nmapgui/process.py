"""Run nmap on a pseudo-terminal.

Without a terminal nmap emits no periodic `--stats-every` estimates at all —
verified, not assumed — so there is no live progress and no countdown, and its
runtime keys do nothing. A pty fixes all three.

  * Linux and macOS: fork + openpty, below.
  * Windows: a ConPTY through the optional `pywinpty` package, if installed.
  * Anywhere else, or if that package is missing: the caller falls back to
    QProcess, which still streams results (they come from the XML) but cannot
    show a countdown.
"""
from __future__ import annotations

import os
import signal
import sys

from PyQt6.QtCore import QObject, QSocketNotifier, QThread, QTimer, pyqtSignal

IS_WINDOWS = sys.platform.startswith("win")
HAVE_PTY = (not IS_WINDOWS) and hasattr(os, "fork") and hasattr(os, "openpty")

if HAVE_PTY:
    import errno
    import fcntl
    import struct
    import termios


def have_winpty() -> bool:
    """Whether the optional Windows ConPTY backend is importable."""
    if not IS_WINDOWS:
        return False
    try:
        import winpty                                    # noqa: F401
        return True
    except Exception:                                    # noqa: BLE001
        return False


def _die_with_parent() -> None:
    """Ask the kernel to SIGTERM this child if the GUI ever dies unexpectedly.

    Without it, os.setsid() below would leave a long scan running headless after
    a crash or a kill -9. Linux only; elsewhere this is a no-op.
    """
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGTERM, 0, 0, 0)     # PR_SET_PDEATHSIG
    except (OSError, AttributeError, ImportError):
        pass


class PtyProcess(QObject):
    """A minimal QProcess-shaped wrapper around fork + pty."""

    output = pyqtSignal(str)
    finished = pyqtSignal(int)          # exit code
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pid = 0
        self._master = -1
        self._notifier: QSocketNotifier | None = None
        self._reaper = QTimer(self)
        self._reaper.setInterval(400)
        self._reaper.timeout.connect(self._poll_child)
        self._exited = False
        self._carry = ""

    # ------------------------------------------------------------------ run
    def start(self, argv: list[str], columns: int = 200, rows: int = 50) -> bool:
        if not HAVE_PTY:
            self.failed.emit("Pseudo-terminals are not available on this platform.")
            return False
        try:
            master, slave = os.openpty()
        except OSError as exc:
            self.failed.emit(f"Could not allocate a pseudo-terminal: {exc}")
            return False

        # A wide, fixed window keeps nmap from wrapping its tables awkwardly.
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, columns, 0, 0))
            attrs = termios.tcgetattr(slave)
            attrs[3] &= ~termios.ECHO      # do not echo the keys we send back at us
            termios.tcsetattr(slave, termios.TCSANOW, attrs)
        except OSError:
            pass

        try:
            pid = os.fork()
        except OSError as exc:
            os.close(master)
            os.close(slave)
            self.failed.emit(f"Could not start nmap: {exc}")
            return False

        if pid == 0:                       # ---- child
            try:
                _die_with_parent()
                os.setsid()
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
                os.dup2(slave, 0)
                os.dup2(slave, 1)
                os.dup2(slave, 2)
                if slave > 2:
                    os.close(slave)
                os.close(master)
                os.execvp(argv[0], argv)
            except BaseException:
                os._exit(127)
            os._exit(127)

        # ---- parent
        os.close(slave)
        self.pid = pid
        self._master = master
        self._exited = False
        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._notifier = QSocketNotifier(master, QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._on_readable)
        self._reaper.start()
        return True

    # ---------------------------------------------------------------- state
    def is_running(self) -> bool:
        return bool(self.pid) and not self._exited

    def write(self, data: bytes) -> None:
        if self._master >= 0 and self.is_running():
            try:
                os.write(self._master, data)
            except OSError:
                pass

    def send_signal(self, sig: int, group: bool = True) -> bool:
        if not self.is_running():
            return False
        try:
            os.killpg(os.getpgid(self.pid), sig) if group else os.kill(self.pid, sig)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(self.pid, sig)
                return True
            except OSError:
                return False

    def terminate(self) -> None:
        self.send_signal(signal.SIGTERM)

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)

    # ------------------------------------------------------------------- io
    def _on_readable(self) -> None:
        if self._master < 0:
            return
        try:
            chunk = os.read(self._master, 65536)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return
            # EIO is how a pty reports "the child closed the other end".
            self._finish()
            return
        if not chunk:
            self._finish()
            return
        text = chunk.decode("utf-8", "replace")
        # A pty gives CRLF; normalise so the views and regexes see plain lines.
        text = (self._carry + text).replace("\r\n", "\n")
        self._carry = ""
        if text.endswith("\r"):
            self._carry, text = "\r", text[:-1]
        self.output.emit(text.replace("\r", "\n"))

    def _poll_child(self) -> None:
        """Backstop: notice an exit even if the pty never reports EIO."""
        if not self.pid or self._exited:
            return
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self._finish()
            return
        if pid == self.pid:
            self._finish(status)

    def _finish(self, status: int | None = None) -> None:
        if self._exited:
            return
        self._exited = True
        self._reaper.stop()
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
            self._notifier = None

        # Drain anything still sitting in the pty buffer.
        if self._master >= 0:
            while True:
                try:
                    chunk = os.read(self._master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.output.emit(chunk.decode("utf-8", "replace").replace("\r\n", "\n"))
            try:
                os.close(self._master)
            except OSError:
                pass
            self._master = -1

        if status is None:
            try:
                _, status = os.waitpid(self.pid, 0)
            except (ChildProcessError, OSError):
                status = 0

        if os.WIFEXITED(status):
            code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            code = -os.WTERMSIG(status)
        else:
            code = 0
        self.finished.emit(code)


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------

class _WinReader(QThread):
    """Blocking reads off the ConPTY, handed back to the GUI thread."""

    chunk = pyqtSignal(str)
    eof = pyqtSignal()

    def __init__(self, pty, parent=None):
        super().__init__(parent)
        self._pty = pty
        self._stop = False

    def run(self) -> None:
        while not self._stop:
            try:
                data = self._pty.read(8192)
            except EOFError:
                break
            except Exception:                            # noqa: BLE001
                break
            if data:
                self.chunk.emit(data)
            elif not self._pty.isalive():
                break
        self.eof.emit()

    def stop(self) -> None:
        self._stop = True


class WinPtyProcess(QObject):
    """The same shape as PtyProcess, backed by a Windows ConPTY."""

    output = pyqtSignal(str)
    finished = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pid = 0
        self._pty = None
        self._reader: _WinReader | None = None
        self._exited = False

    def start(self, argv: list[str], columns: int = 200, rows: int = 50) -> bool:
        try:
            import winpty
        except Exception as exc:                          # noqa: BLE001
            self.failed.emit(f"pywinpty is not available: {exc}")
            return False
        try:
            self._pty = winpty.PtyProcess.spawn(argv, dimensions=(rows, columns))
        except Exception as exc:                          # noqa: BLE001
            self.failed.emit(f"Could not start nmap: {exc}")
            return False

        self.pid = getattr(self._pty, "pid", 0) or 0
        self._exited = False
        self._reader = _WinReader(self._pty, self)
        self._reader.chunk.connect(self._on_chunk)
        self._reader.eof.connect(self._finish)
        self._reader.start()
        return True

    # ----------------------------------------------------------------- state
    def is_running(self) -> bool:
        try:
            return bool(self._pty) and not self._exited and self._pty.isalive()
        except Exception:                                 # noqa: BLE001
            return False

    def write(self, data: bytes) -> None:
        if self.is_running():
            try:
                self._pty.write(data.decode("utf-8", "replace"))
            except Exception:                             # noqa: BLE001
                pass

    def send_signal(self, sig: int, group: bool = True) -> bool:
        return False            # Windows has no SIGSTOP/SIGCONT to send

    def terminate(self) -> None:
        if self._pty is not None:
            try:
                self._pty.terminate(force=False)
            except Exception:                             # noqa: BLE001
                pass

    def kill(self) -> None:
        if self._pty is not None:
            try:
                self._pty.terminate(force=True)
            except Exception:                             # noqa: BLE001
                pass

    # -------------------------------------------------------------- internals
    def _on_chunk(self, text: str) -> None:
        self.output.emit(text.replace("\r\n", "\n").replace("\r", "\n"))

    def _finish(self) -> None:
        if self._exited:
            return
        self._exited = True
        if self._reader is not None:
            self._reader.stop()
            self._reader.wait(1500)
        code = 0
        try:
            code = int(self._pty.exitstatus or 0)
        except Exception:                                 # noqa: BLE001
            code = 0
        self.finished.emit(code)
