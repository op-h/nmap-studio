#!/usr/bin/env bash
# Build NmapStudio-Setup.exe. Runs on Linux (makensis) or on Windows.
#
#   sudo apt install nsis        # if makensis is missing
#   ./packaging/build-windows-installer.sh
#
# If dist/NmapStudio.exe exists it is bundled, and the installed program needs
# nothing but nmap. Otherwise the installer ships the Python sources and uses
# the Python on the target machine.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

command -v makensis >/dev/null 2>&1 || {
    echo "makensis not found.  sudo apt install nsis"; exit 1; }

[ -f nmapgui/assets/icon.ico ] || python3 "$HERE/make-icons.py"
mkdir -p dist

# Everything the installed program needs travels with it, unless told otherwise.
if [ "${BUNDLE:-1}" = "1" ]; then
    [ -f build/winruntime/pythonw.exe ] || "$HERE/fetch-windows-runtime.sh"
    [ -f build/winnmap/nmap.exe ]       || "$HERE/fetch-windows-nmap.sh"
fi

echo "==> installer contents:"
[ -f dist/NmapStudio.exe ]          && echo "    frozen NmapStudio.exe (Python not needed)"
[ -f build/winruntime/pythonw.exe ] && echo "    private Python + PyQt6  ($(du -sh build/winruntime | cut -f1))"
[ -f build/winnmap/nmap.exe ]       && echo "    nmap + NSE scripts      ($(du -sh build/winnmap | cut -f1))"
if [ ! -f build/winruntime/pythonw.exe ] && [ ! -f dist/NmapStudio.exe ]; then
    echo "    sources only - the target machine needs its own Python + PyQt6"
fi

makensis -V2 -DROOT="$ROOT" "$HERE/windows-installer.nsi"

echo
echo "==> dist/NmapStudio-Setup.exe  ($(du -h dist/NmapStudio-Setup.exe | cut -f1))"
echo "Copy it to a Windows machine and double-click it."
