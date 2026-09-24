#!/usr/bin/env bash
# Build a .deb you can install with:   sudo apt install ./dist/nmap-studio_*.deb
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/nmapgui/__init__.py")"
VERSION="${VERSION:-1.0}"
PKG="nmap-studio"
BUILD="$ROOT/build/deb"
DIST="$ROOT/dist"

# --bundled ships a self-contained build: Python and Qt travel inside the
# package, so it installs on a machine that has neither.
BUNDLED=0
ARCH="all"
DEPENDS="python3 (>= 3.10), python3-pyqt6, nmap"
SUFFIX=""
for arg in "$@"; do
    case "$arg" in
        --bundled)
            BUNDLED=1
            ARCH="$(dpkg --print-architecture)"
            DEPENDS="nmap"
            SUFFIX="-bundled"
            ;;
        *) echo "unknown option: $arg"; exit 1 ;;
    esac
done
PKGNAME="$PKG$SUFFIX"

echo "==> building $PKGNAME $VERSION ($ARCH)"
rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" \
         "$BUILD/usr/lib/$PKG" \
         "$BUILD/usr/bin" \
         "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/doc/$PKG"

# ---- the application itself
if [ "$BUNDLED" = "1" ]; then
    if [ ! -x "$ROOT/dist/nmap-studio" ]; then
        echo "==> building the self-contained binary first"
        "$HERE/build-linux-binary.sh"
    fi
    cp "$ROOT/dist/nmap-studio" "$BUILD/usr/lib/$PKG/nmap-studio-bin"
    chmod 755 "$BUILD/usr/lib/$PKG/nmap-studio-bin"
else
    cp -r "$ROOT/nmapgui" "$BUILD/usr/lib/$PKG/"
    cp "$ROOT/selftest.py" "$BUILD/usr/lib/$PKG/"
    cp "$ROOT/nmap-studio" "$BUILD/usr/lib/$PKG/nmap-studio"
    chmod 755 "$BUILD/usr/lib/$PKG/nmap-studio"
    find "$BUILD/usr/lib/$PKG" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
fi

# ---- generate the icons if they are missing, then install them
if [ ! -f "$ROOT/nmapgui/assets/icon-256.png" ]; then
    python3 "$HERE/make-icons.py"
fi
for size in 16 24 32 48 64 128 256 512; do
    dir="$BUILD/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    cp "$ROOT/nmapgui/assets/icon-${size}.png" "$dir/$PKG.png"
done

# ---- launcher on PATH
# The real launcher lives beside the package so its imports resolve; this is
# just the thin entry on PATH.
if [ "$BUNDLED" = "1" ]; then
    cat > "$BUILD/usr/bin/$PKG" <<'LAUNCH'
#!/bin/sh
exec /usr/lib/nmap-studio/nmap-studio-bin "$@"
LAUNCH
else
    cat > "$BUILD/usr/bin/$PKG" <<'LAUNCH'
#!/bin/sh
exec python3 /usr/lib/nmap-studio/nmap-studio "$@"
LAUNCH
fi
chmod 755 "$BUILD/usr/bin/$PKG"

# ---- desktop entry
cat > "$BUILD/usr/share/applications/$PKG.desktop" <<DESKTOP
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

# ---- docs
cp "$ROOT/README.md" "$BUILD/usr/share/doc/$PKG/"
cat > "$BUILD/usr/share/doc/$PKG/copyright" <<'COPY'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Nmap Studio

Files: *
Copyright: oph <https://github.com/op-h>
License: MIT

Nmap Studio is a front-end only. nmap itself is a separate program by Gordon
Lyon and the Nmap project, and is installed as a dependency of this package.
COPY
gzip -9n -c "$ROOT/README.md" > "$BUILD/usr/share/doc/$PKG/changelog.gz"

# ---- control
INSTALLED_KB="$(du -sk "$BUILD" | cut -f1)"
cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: $PKGNAME
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Depends: $DEPENDS
Recommends: policykit-1
Conflicts: ${PKG}${SUFFIX:+, }${SUFFIX:+nmap-studio}
Provides: nmap-studio
Installed-Size: $INSTALLED_KB
Maintainer: oph <https://github.com/op-h>
Homepage: https://github.com/op-h
Description: Graphical front-end for nmap
 Nmap Studio puts every nmap option, timing control, evasion setting and NSE
 script behind a searchable interface, and shows results as the scan runs.
 .
 It includes a progress ring with a live countdown to the finish, host and
 port views that fill in while nmap works, a topology map built from
 traceroute data, NSE script output with vulnerable findings highlighted,
 a searchable scan history that can diff two runs, and export to HTML, CSV,
 JSON, Markdown and nmap XML.
CONTROL

cat > "$BUILD/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
    fi
fi
exit 0
POSTINST

cat > "$BUILD/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    rm -rf /usr/lib/nmap-studio/nmapgui/__pycache__ \
           /usr/lib/nmap-studio/nmapgui/widgets/__pycache__ 2>/dev/null || true
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
fi
exit 0
POSTRM

chmod 755 "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm"
find "$BUILD/usr" -type d -exec chmod 755 {} +
find "$BUILD/usr" -type f -exec chmod 644 {} +
chmod 755 "$BUILD/usr/bin/$PKG"
[ -f "$BUILD/usr/lib/$PKG/nmap-studio" ] && chmod 755 "$BUILD/usr/lib/$PKG/nmap-studio"
[ -f "$BUILD/usr/lib/$PKG/nmap-studio-bin" ] && chmod 755 "$BUILD/usr/lib/$PKG/nmap-studio-bin"

mkdir -p "$DIST"
DEB="$DIST/${PKGNAME}_${VERSION}_${ARCH}.deb"
if command -v fakeroot >/dev/null 2>&1; then
    fakeroot dpkg-deb --build --root-owner-group "$BUILD" "$DEB" >/dev/null
else
    dpkg-deb --build --root-owner-group "$BUILD" "$DEB" >/dev/null
fi

echo "==> $DEB  ($(du -h "$DEB" | cut -f1))"
echo
echo "Install it with:"
echo "    sudo apt install $DEB"
[ "$BUNDLED" = "1" ] && echo "    (Python and Qt are inside the package - only nmap is a dependency.)"
echo "Then launch it from your application menu, or run:  nmap-studio"
