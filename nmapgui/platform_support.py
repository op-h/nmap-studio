"""Everything that differs between Windows, Linux and macOS, in one place."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
IS_POSIX = not IS_WINDOWS


# --------------------------------------------------------------------------
# finding nmap
# --------------------------------------------------------------------------

def app_root() -> str:
    """The directory the application was installed into."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return frozen
    # .../<root>/nmapgui/platform_support.py  ->  <root>
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled_nmap() -> str:
    """nmap shipped alongside the app, as the Windows installer does."""
    name = "nmap.exe" if IS_WINDOWS else "nmap"
    for base in (app_root(), os.path.dirname(app_root())):
        candidate = os.path.join(base, "nmap", name)
        if os.path.isfile(candidate):
            return candidate
    return ""

_WINDOWS_NMAP_DIRS = [
    r"C:\Program Files (x86)\Nmap",
    r"C:\Program Files\Nmap",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Nmap"),
]

_POSIX_NMAP_PATHS = [
    "/usr/bin/nmap", "/usr/local/bin/nmap", "/opt/homebrew/bin/nmap",
    "/snap/bin/nmap", "/usr/sbin/nmap",
]


def find_nmap() -> str:
    """Absolute path to nmap, or the bare name if it cannot be located.

    A copy shipped with the app wins, so an install that bundles nmap does not
    depend on anything being on PATH. Windows installers in particular often
    leave Nmap off PATH, so the usual install directories are checked too.
    """
    bundled = bundled_nmap()
    if bundled:
        return bundled
    found = shutil.which("nmap")
    if found:
        return found
    if IS_WINDOWS:
        for directory in _WINDOWS_NMAP_DIRS:
            candidate = os.path.join(directory, "nmap.exe")
            if os.path.isfile(candidate):
                return candidate
        return "nmap.exe"
    for candidate in _POSIX_NMAP_PATHS:
        if os.path.isfile(candidate):
            return candidate
    return "nmap"


def nmap_exists(path: str) -> bool:
    return bool(path) and (os.path.isfile(path) or shutil.which(path) is not None)


# --------------------------------------------------------------------------
# privileges
# --------------------------------------------------------------------------

def is_elevated() -> bool:
    """True when raw sockets are available: root on POSIX, Administrator on Windows."""
    if IS_WINDOWS:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:                                  # noqa: BLE001
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def elevation_helpers() -> list[str]:
    """Ways this machine can raise privileges, best first."""
    if IS_WINDOWS:
        return ["uac"] if shutil.which("powershell") else []
    helpers = []
    for name in ("pkexec", "sudo", "doas"):
        if shutil.which(name):
            helpers.append(name)
    return helpers


def privileged_argv(argv: list[str], helper: str) -> list[str]:
    """Wrap a command so it runs with privileges, keeping its arguments intact."""
    if helper == "pkexec" and shutil.which("pkexec"):
        return ["pkexec", "--disable-internal-agent"] + argv
    if helper == "sudo" and shutil.which("sudo"):
        return ["sudo", "-n"] + argv
    if helper == "doas" and shutil.which("doas"):
        return ["doas"] + argv
    return argv


def elevation_hint() -> str:
    """What to tell someone who needs privileges but has no helper available."""
    if IS_WINDOWS:
        return ("Close Nmap Studio and start it again with “Run as administrator”. "
                "Raw-socket scans (-sS, -O, --traceroute) need that on Windows, and "
                "Npcap must be installed.")
    if IS_MAC:
        return "Start it from a terminal with: sudo ./nmap-studio"
    return ("Install pkexec (policykit-1) or sudo, or start Nmap Studio from a root "
            "shell.")


def can_pause() -> bool:
    """Windows has no SIGSTOP, so a running scan cannot be suspended there."""
    return IS_POSIX


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

def config_dir() -> str:
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
        return os.path.join(base, "NmapStudio")
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support/nmapgui")
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "nmapgui")


def script_dirs() -> list[str]:
    """Where NSE scripts live, most likely first."""
    dirs = []
    bundled = bundled_nmap()
    if bundled:
        dirs.append(os.path.join(os.path.dirname(bundled), "scripts"))
    return dirs + _system_script_dirs()


def _system_script_dirs() -> list[str]:
    if IS_WINDOWS:
        dirs = [os.path.join(d, "scripts") for d in _WINDOWS_NMAP_DIRS]
        nmap = find_nmap()
        if os.path.isfile(nmap):
            dirs.insert(0, os.path.join(os.path.dirname(nmap), "scripts"))
        return dirs
    return [
        "/usr/share/nmap/scripts",
        "/usr/local/share/nmap/scripts",
        "/opt/homebrew/share/nmap/scripts",
        os.path.expanduser("~/.nmap/scripts"),
    ]


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------

def no_window_flags() -> int:
    """CREATE_NO_WINDOW, so scans do not flash a console window on Windows."""
    if IS_WINDOWS:
        return 0x08000000
    return 0


def open_url(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


def has_manpage() -> bool:
    return IS_POSIX and shutil.which("man") is not None
