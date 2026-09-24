#!/usr/bin/env bash
# Install Nmap Studio on any Linux that is not Debian-based.
# (On Debian, Ubuntu, Kali or Mint, build the .deb instead — see README.)
#
#   sudo ./packaging/install.sh            install to /usr/local
#   ./packaging/install.sh --user          install just for you, no sudo
#   sudo ./packaging/install.sh --uninstall
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
PKG="nmap-studio"

MODE="system"
ACTION="install"
for arg in "$@"; do
    case "$arg" in
        --user)      MODE="user" ;;
        --uninstall) ACTION="uninstall" ;;
        -h|--help)   sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "unknown option: $arg"; exit 1 ;;
    esac
done

if [ "$MODE" = "user" ]; then
    PREFIX="$HOME/.local"
else
    PREFIX="/usr/local"
    if [ "$(id -u)" != "0" ]; then
        echo "System-wide install needs root:   sudo $0"
        echo "Or install just for yourself:     $0 --user"
        exit 1
    fi
fi

LIBDIR="$PREFIX/lib/$PKG"
BINDIR="$PREFIX/bin"
APPDIR="$PREFIX/share/applications"
ICONDIR="$PREFIX/share/icons/hicolor"

if [ "$ACTION" = "uninstall" ]; then
    echo "==> removing Nmap Studio from $PREFIX"
    rm -rf "$LIBDIR"
    rm -f "$BINDIR/$PKG" "$APPDIR/$PKG.desktop"
    for size in 16 24 32 48 64 128 256 512; do
        rm -f "$ICONDIR/${size}x${size}/apps/$PKG.png"
    done
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$APPDIR" || true
    echo "==> done. Your scans and settings in ~/.config/nmapgui were kept."
    exit 0
fi

# ---- dependency check (advice only; nothing is installed for you)
missing=""
python3 - <<'PY' >/dev/null 2>&1 || missing="$missing python3-pyqt6"
import PyQt6.QtWidgets
PY
command -v nmap >/dev/null 2>&1 || missing="$missing nmap"
if [ -n "$missing" ]; then
    echo "Missing dependencies:$missing"
    echo "Install them first, for example:"
    echo "    Fedora:   sudo dnf install nmap python3-pyqt6"
    echo "    Arch:     sudo pacman -S nmap python-pyqt6"
    echo "    openSUSE: sudo zypper install nmap python3-qt6"
    exit 1
fi

echo "==> installing Nmap Studio into $PREFIX"
install -d "$LIBDIR" "$BINDIR" "$APPDIR"
cp -r "$ROOT/nmapgui" "$LIBDIR/"
install -m 755 "$ROOT/nmap-studio" "$LIBDIR/nmap-studio"
install -m 644 "$ROOT/selftest.py" "$LIBDIR/selftest.py"
find "$LIBDIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

if [ ! -f "$ROOT/nmapgui/assets/icon-256.png" ]; then
    python3 "$HERE/make-icons.py"
fi
for size in 16 24 32 48 64 128 256 512; do
    install -d "$ICONDIR/${size}x${size}/apps"
    install -m 644 "$ROOT/nmapgui/assets/icon-${size}.png" \
            "$ICONDIR/${size}x${size}/apps/$PKG.png"
done

cat > "$BINDIR/$PKG" <<LAUNCH
#!/bin/sh
exec python3 "$LIBDIR/nmap-studio" "\$@"
LAUNCH
chmod 755 "$BINDIR/$PKG"

cat > "$APPDIR/$PKG.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=Nmap Studio
GenericName=Network Scanner
Comment=Graphical front-end for nmap with live results and reports
Exec=$PKG %f
Icon=$PKG
Terminal=false
Categories=Network;Security;System;
Keywords=nmap;scan;network;ports;security;portscan;
MimeType=text/xml;
StartupNotify=true
StartupWMClass=nmap-studio
DESKTOP

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q "$APPDIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q -f "$ICONDIR" || true

echo "==> installed."
echo "    Launch it from your application menu, or run:  $PKG"
if [ "$MODE" = "user" ] && ! echo ":$PATH:" | grep -q ":$BINDIR:"; then
    echo
    echo "    Note: $BINDIR is not on your PATH. Add this to ~/.bashrc:"
    echo "        export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
