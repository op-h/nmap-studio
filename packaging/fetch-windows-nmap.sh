#!/usr/bin/env bash
# Put nmap's own Windows files into build/winnmap/ so the installer can carry
# them, and nothing has to be downloaded on the target machine.
#
# What this takes from the official nmap installer: nmap.exe, the DLLs it needs,
# the service/OS databases and the whole NSE library, plus nmap's licences.
#
# What it deliberately does NOT take: Npcap. Npcap's licence does not allow
# redistribution, so anyone who needs raw-socket scans (-sS, -O, --traceroute)
# installs it themselves from https://npcap.com. Everything else — connect
# scans, version detection, all 600+ NSE scripts — works without it.
set -euo pipefail

NMAPVER="${NMAPVER:-7.99}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
CACHE="$ROOT/build/wincache"
WORK="$ROOT/build/nmapextract"
OUT="$ROOT/build/winnmap"

command -v 7z >/dev/null 2>&1 || {
    echo "7z is needed to unpack the nmap installer.  sudo apt install p7zip-full"
    exit 1; }

mkdir -p "$CACHE"
SETUP="$CACHE/nmap-$NMAPVER-setup.exe"
if [ ! -f "$SETUP" ]; then
    echo "==> downloading nmap $NMAPVER for Windows"
    curl -fL --progress-bar "https://nmap.org/dist/nmap-$NMAPVER-setup.exe" -o "$SETUP"
fi

echo "==> unpacking"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"
7z x -y -o"$WORK" "$SETUP" > /dev/null

echo "==> selecting the files nmap needs at runtime"
for item in nmap.exe \
            nmap-services nmap-os-db nmap-service-probes nmap-protocols \
            nmap-rpc nmap-mac-prefixes nmap-payloads \
            nse_main.lua ca-bundle.crt \
            LICENSE 3rd-party-licenses.txt; do
    [ -e "$WORK/$item" ] && cp -r "$WORK/$item" "$OUT/" || true
done
cp "$WORK"/*.dll "$OUT/" 2>/dev/null || true
cp -r "$WORK/scripts" "$OUT/" 2>/dev/null || true
cp -r "$WORK/nselib" "$OUT/" 2>/dev/null || true
cp -r "$WORK/licenses" "$OUT/" 2>/dev/null || true

# Npcap must never end up in the bundle.
find "$OUT" -iname "*npcap*" -delete 2>/dev/null || true

echo
echo "==> bundled nmap: $OUT  ($(du -sh "$OUT" | cut -f1))"
echo "    nmap.exe:     $([ -f "$OUT/nmap.exe" ] && echo yes || echo NO)"
echo "    NSE scripts:  $(ls "$OUT/scripts" 2>/dev/null | wc -l)"
echo "    npcap files:  $(find "$OUT" -iname '*npcap*' | wc -l)  (must be 0)"
