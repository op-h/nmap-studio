#!/usr/bin/env bash
# Build a single-file Linux executable (for distros without .deb support).
# Produces: dist/nmap-studio
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

command -v pyinstaller >/dev/null 2>&1 || {
    echo "pyinstaller is not installed.  pip install pyinstaller"; exit 1; }

python3 "$HERE/make-icons.py"
pyinstaller --noconfirm --clean "$HERE/nmap-studio.spec"

echo
echo "==> dist/nmap-studio  ($(du -h dist/nmap-studio | cut -f1))"
echo "Copy it anywhere and run it. nmap itself must still be installed."
