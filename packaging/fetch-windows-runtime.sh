#!/usr/bin/env bash
# Download a private Python + PyQt6 for Windows into build/winruntime/.
#
# The Windows installer bundles this, so whoever installs Nmap Studio does not
# have to install Python or PyQt6 themselves. Run it on any machine with a
# network connection — it downloads Windows files, it does not run them.
set -euo pipefail

PYVER="${PYVER:-3.12.7}"
PYTAG="${PYTAG:-cp312}"
PYSHORT="$(echo "$PYVER" | cut -d. -f1,2 | tr -d '.')"    # 3.12.7 -> 312

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
OUT="$ROOT/build/winruntime"
CACHE="$ROOT/build/wincache"

mkdir -p "$CACHE"

echo "==> Python $PYVER (embeddable, 64-bit)"
ZIP="$CACHE/python-$PYVER-embed-amd64.zip"
if [ ! -f "$ZIP" ]; then
    curl -fL --progress-bar \
        "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip" \
        -o "$ZIP"
fi
rm -rf "$OUT"
mkdir -p "$OUT"
unzip -q "$ZIP" -d "$OUT"

echo "==> PyQt6 wheels for Windows"
pip download --quiet --no-deps --only-binary=:all: \
    --platform win_amd64 --python-version "${PYVER%.*}" \
    --dest "$CACHE" PyQt6 PyQt6-Qt6 PyQt6_sip

SITE="$OUT/Lib/site-packages"
mkdir -p "$SITE"
for whl in "$CACHE"/*win_amd64.whl; do
    [ -f "$whl" ] || continue
    name="$(basename "$whl")"
    # PyQt6 itself ships as cp39-abi3 (stable ABI, valid on any newer Python),
    # PyQt6-Qt6 as py3-none, and PyQt6-sip as a version-specific cp3xx build.
    case "$name" in
        *abi3*|*-py3-none-win_amd64.whl|*"$PYTAG"*)
            echo "    unpacking $name"
            unzip -q -o "$whl" -d "$SITE"
            ;;
        *) echo "    skipping  $name (built for another Python)" ;;
    esac
done

# The embeddable build ignores site-packages unless its ._pth says otherwise.
{
    echo "python$PYSHORT.zip"
    echo "."
    echo "Lib\\site-packages"
    echo "import site"
} > "$OUT/python$PYSHORT._pth"

# Trim what a GUI front-end never touches, to keep the installer small.
rm -rf "$SITE"/PyQt6/Qt6/qml \
       "$SITE"/PyQt6/Qt6/translations \
       "$SITE"/PyQt6/Qt6/plugins/qmltooling \
       "$SITE"/PyQt6/Qt6/plugins/sqldrivers \
       "$SITE"/PyQt6/Qt6/plugins/multimedia \
       "$SITE"/PyQt6/Qt6/plugins/designer 2>/dev/null || true
for pattern in Qt6WebEngine Qt6Quick Qt6Qml Qt6Pdf Qt6Designer Qt63D Qt6Charts \
               Qt6DataVisualization Qt6Multimedia Qt6Bluetooth Qt6Nfc Qt6Sql \
               Qt6Test Qt6Help Qt6RemoteObjects Qt6Sensors Qt6SerialPort \
               Qt6Positioning Qt6WebSockets Qt6WebChannel; do
    rm -f "$SITE"/PyQt6/Qt6/bin/"$pattern"*.dll 2>/dev/null || true
done
find "$SITE" -name "*.pyi" -delete 2>/dev/null || true
find "$SITE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo
echo "==> runtime ready: $OUT  ($(du -sh "$OUT" | cut -f1))"
echo "    pythonw.exe present: $([ -f "$OUT/pythonw.exe" ] && echo yes || echo NO)"
echo "    PyQt6 present:       $([ -d "$SITE/PyQt6" ] && echo yes || echo NO)"
echo "    QtWidgets present:   $([ -f "$SITE/PyQt6/QtWidgets.pyd" ] && echo yes || echo NO)"
