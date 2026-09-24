# Changelog

## 1.0 — 2026-09

First release.

**Scanning**
- Every nmap option (100 flags) in a searchable builder, each one explained
- Command line and option panel stay in sync, in both directions
- 16 scan profiles, plus your own
- All installed NSE scripts, with their documentation and risk level
- Several scans at once in tabs; stop, pause and resume

**While it runs**
- Progress ring with a live countdown, phase, elapsed time and finish time
- Hosts, ports and script output appear as nmap finds them
- nmap runs on a pseudo-terminal, which is what makes live progress possible

**Results**
- Seven views: Output, Hosts, Ports, Scripts, Topology, Summary, XML
- Topology map drawn from traceroute data
- Scan history in SQLite; reopen a past scan or diff two runs
- Export to HTML, CSV, JSON, Markdown and nmap XML

**Packaging**
- Debian package with Python and Qt inside — only nmap is a dependency
- Windows installer carrying Python, Qt and nmap; nothing else to download
- Single-file builds for Linux and Windows
