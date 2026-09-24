# Third-party notices

Nmap Studio itself is MIT licensed — see [LICENSE](LICENSE).
It is a **front-end**: it contains no nmap source code and re-implements
nothing that nmap does.

## nmap

Copyright Nmap Software LLC, distributed under the
[Nmap Public Source License](https://nmap.org/npsl/).

- Running from source, or from the Debian package: nmap is installed
  separately by your package manager. Nothing is redistributed here.
- The Windows installer, when built, bundles **unmodified** official nmap
  binaries and data files so the program works without a separate download.
  nmap's own `LICENSE` and `3rd-party-licenses.txt` are installed alongside
  them.

## Npcap

**Not bundled, anywhere.** Npcap's licence does not permit redistribution, so
no build of Nmap Studio includes it. It is only needed on Windows for
raw-socket scans (`-sS`, `-O`, `--traceroute`); install it yourself from
[npcap.com](https://npcap.com) if you want those.

The Windows build script asserts that zero Npcap files end up in the bundle.

## Qt and PyQt6

Qt 6 is used through [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
under the GPL v3. The Debian package and the source install use the PyQt6
already on your system. The bundled Windows and single-file Linux builds
include PyQt6 and the Qt libraries, and the full corresponding source of this
application is in this repository.
