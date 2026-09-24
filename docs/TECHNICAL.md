<div align="center">

<img src="../nmapgui/assets/icon-128.png" width="88" alt="Nmap Studio">

# Nmap Studio — Technical Documentation

**Version 1.0** · Designed and built by [oph](https://github.com/op-h)

</div>

---

## Contents

1. [What this is](#1-what-this-is)
2. [Architecture](#2-architecture)
3. [Every module](#3-every-module)
4. [How a scan runs](#4-how-a-scan-runs)
5. [The countdown, and why it needs a terminal](#5-the-countdown-and-why-it-needs-a-terminal)
6. [Parsing nmap](#6-parsing-nmap)
7. [The option catalogue](#7-the-option-catalogue)
8. [NSE script handling](#8-nse-script-handling)
9. [Storage](#9-storage)
10. [The design system](#10-the-design-system)
11. [Cross-platform behaviour](#11-cross-platform-behaviour)
12. [Privileges](#12-privileges)
13. [Building the packages](#13-building-the-packages)
14. [Testing](#14-testing)
15. [Extending it](#15-extending-it)

---

## 1. What this is

Nmap Studio is a desktop front-end for [nmap](https://nmap.org). It does not
re-implement any scanning: it builds an nmap command line, runs the real nmap
binary, and presents what comes back.

**Stack**

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | nmap's output is text and XML; this is a parsing job |
| GUI | PyQt6 (Qt 6) | Native widgets, real tables and trees, no browser engine |
| Process | POSIX pty / Windows ConPTY / QProcess | nmap only reports progress to a terminal |
| Results | nmap XML, parsed incrementally | Structured, and written while the scan is still running |
| Storage | SQLite + JSON | History needs querying; settings do not |
| Drawing | QPainter | Icons, the progress ring and the topology map are all vector, no image assets |

There are **no third-party Python dependencies** beyond PyQt6. No requests, no
numpy, no chart library.

---

## 2. Architecture

```
                    ┌──────────────────────────────────────┐
                    │            MainWindow                │
                    │  toolbar · menus · docks · toasts    │
                    └───────────────┬──────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼────────┐        ┌─────────▼─────────┐       ┌─────────▼────────┐
│  OptionBuilder │        │     ScanTab       │       │  Sidebar panels  │
│  ScriptBrowser │        │  (one per scan)   │       │ profiles/history │
└───────┬────────┘        └─────────┬─────────┘       └──────────────────┘
        │                           │
        │ builds                    │ owns
        ▼                           ▼
┌────────────────┐        ┌───────────────────┐
│   ScanConfig   │───────▶│    ScanRunner     │
│  opts, scripts │  argv  │  state machine    │
└────────────────┘        └─────────┬─────────┘
                                    │ spawns
                    ┌───────────────┴───────────────┐
                    │                               │
          ┌─────────▼─────────┐          ┌──────────▼─────────┐
          │    PtyProcess     │          │      QProcess      │
          │ (Linux / macOS)   │          │    (fallback)      │
          │  WinPtyProcess    │          │                    │
          └─────────┬─────────┘          └──────────┬─────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │  stdout          XML file
                                    ▼                     │
                          ┌──────────────────┐            │
                          │ scrape_progress  │            │
                          └────────┬─────────┘            │
                                   │                      ▼
                                   │            ┌──────────────────┐
                                   │            │  parse_xml_text  │
                                   │            │ (partial-safe)   │
                                   │            └────────┬─────────┘
                                   ▼                     ▼
                          ┌─────────────────────────────────────┐
                          │  ScanHeader · Hosts · Ports ·       │
                          │  Scripts · Topology · Summary · XML │
                          └─────────────────────────────────────┘
```

**The rule that shapes everything:** results come from the **XML**, progress
comes from **stdout**. They are independent, so a failure in one does not blank
the other. If nmap never reports progress (no terminal), results still stream
in; if the XML is half-written, the parser repairs it.

---

## 3. Every module

### Core

| File | Lines | Responsibility |
|---|---|---|
| `optionsdata.py` | ~320 | The catalogue: 100 `Opt` rows, 16 profiles, NSE categories and risk levels |
| `command.py` | ~230 | `ScanConfig` → argv, argv → `ScanConfig`, validation, root detection |
| `runner.py` | ~250 | The scan state machine: start/stop/pause, progress, partial results |
| `process.py` | ~300 | pty (fork+openpty), Windows ConPTY, output normalisation, orphan protection |
| `parser.py` | ~330 | nmap XML → dataclasses; progress scraping; partial-document repair |
| `nse.py` | ~150 | NSE catalogue from `script.db`, docs read from the `.nse` sources |
| `storage.py` | ~150 | SQLite history, settings, saved profiles |
| `exporters.py` | ~230 | CSV / JSON / Markdown / HTML, and scan diffing |
| `platform_support.py` | ~170 | Everything that differs between Windows, Linux and macOS |
| `design.py` | ~60 | Spacing, radius, type, motion and elevation tokens |
| `theme.py` | ~330 | Palettes, fonts, the Qt stylesheet |
| `icons.py` | ~260 | 40 vector icons drawn with QPainter |

### Widgets

| File | Responsibility |
|---|---|
| `scantab.py` | One scan: runner + the seven result views |
| `scanheader.py` | Progress ring, countdown, live metrics, scan controls |
| `optionbuilder.py` | The 100 options, generated from the catalogue, with search |
| `scriptbrowser.py` | NSE browser: filter, risk colouring, documentation |
| `hostsview.py` | Host tree + detail panel (addresses, OS, scripts, traceroute) |
| `portstable.py` | Flat sortable table of every port |
| `scriptsview.py` | NSE output grouped by host, VULNERABLE highlighted |
| `topology.py` | Radial network map, laid out as a tree from traceroute data |
| `summaryview.py` | Stat cards, service/software breakdowns, findings |
| `outputview.py` | Terminal pane with syntax colouring and incremental find |
| `sidebar.py` | Profile library and scan history |
| `collapsible.py` | Animated section cards |
| `common.py` | Shared parts: cards, stat blocks, toasts, empty states, `IconField`, `FlowLayout` |

---

## 4. How a scan runs

```
 user presses Scan
        │
        ▼
 ScanConfig.validate()          empty target? bad --mtu? missing -iL file?
        │
        ▼
 ScanConfig.needs_root()        any selected option that needs raw sockets
        │
        ├── needs privileges and we have none
        │        └──▶ offer pkexec / sudo, or run unprivileged, or cancel
        ▼
 ScanConfig.argv(xml_path)      catalogue order + --stats-every 1s + -oX <temp>
        │
        ▼
 ScanRunner.start()
        │
        ├─▶ PtyProcess (fork, openpty, PR_SET_PDEATHSIG, setsid)
        │       └─ QSocketNotifier ─▶ _ingest() ─▶ scrape_progress ─▶ ScanHeader
        │
        └─▶ QTimer 1s ─▶ _poll_xml() ─▶ parse_xml_text ─▶ partial_result
                                                    └──▶ Hosts / Ports / Scripts
        │
        ▼
 process exits ─▶ final XML parse ─▶ full render ─▶ history row written
```

**The state machine** is four states — `idle → running → (paused) → stopping →
idle`. Stop sends `SIGTERM`, then `SIGKILL` after 4 s. Pause is `SIGSTOP` to the
process group; a paused process is sent `SIGCONT` before terminating, because a
stopped process cannot act on `SIGTERM`.

---

## 5. The countdown, and why it needs a terminal

This was the hard part, and the answer is not obvious.

**Verified behaviour:** with stdout redirected to a file or a pipe, nmap emits
**no periodic progress at all** — not buffered, simply not produced. Neither the
`Stats:` lines nor the `<taskprogress>` elements in the XML appear. Give it a
terminal and both appear within a second.

```bash
# no terminal -> zero progress lines, even when allowed to finish
nmap -sT -p1-30000 --stats-every 2s 127.0.0.1 > out.txt
grep -c "Stats:" out.txt          # 0

# a terminal -> progress immediately
script -qfc "nmap -sT -p1-30000 --stats-every 2s 127.0.0.1" /dev/null | grep -c "Stats:"
```

So the process layer gives nmap a real pty:

| Platform | Backend | Countdown |
|---|---|---|
| Linux, macOS | `fork()` + `openpty()` | ✅ always |
| Windows + `pywinpty` | ConPTY | ✅ |
| Windows without it | QProcess | ❌ ring sweeps and elapsed counts instead |

**Two progress sources.** `scrape_progress()` reads stdout:

```
Stats: 0:00:05 elapsed; 0 hosts completed (1 up), 1 undergoing SYN Stealth Scan
SYN Stealth Scan Timing: About 24.63% done; ETC: 15:02 (0:00:12 remaining)
```

and `progress_from_xml()` reads the same estimates out of the XML
(`<taskprogress percent="24.63" remaining="12" etc="…"/>`) whenever stdout gives
nothing. The XML path is the reason the Windows fallback still shows *something*.

**The countdown itself** ticks locally once a second and re-syncs on every fresh
estimate, so it moves smoothly between nmap's updates instead of jumping. When
the estimate runs out during a slow phase it says *wrapping up* rather than
sitting on `0:00`.

**Orphan protection.** The child calls `setsid()` so signals sent to the GUI do
not hit the scan, and `prctl(PR_SET_PDEATHSIG, SIGTERM)` so a crashed GUI cannot
leave a scan running headless.

---

## 6. Parsing nmap

`parser.py` turns XML into dataclasses: `ScanResult → Host → Port → Service`,
plus `OSMatch`, `Hop` and script output.

**Partial documents.** nmap flushes XML host by host, so the file has no closing
tag while the scan runs. `_repair()` cuts at the last complete `</host>` and
appends `</nmaprun>`, which is what makes live results possible:

```python
result = parse_xml_text(open(path).read())   # works mid-scan
```

The poller only re-parses when the file has grown, so a long scan does not
re-parse the same bytes every second.

**Diffing.** `diff_results()` compares two `ScanResult`s and reports ports that
opened, ports that closed, service versions that changed and hosts that appeared
or vanished — the basis of *Compare two* in the history panel.

---

## 7. The option catalogue

Every option is one row:

```python
Opt("sS", "-sS", "TCP SYN (stealth) — the default when root", EXCLUSIVE, "technique",
    "Half-open scan. Fast, accurate and relatively quiet. Needs raw sockets.",
    exclusive="scantype", root=True)
```

From that single row the app derives: the control type (checkbox, radio, text,
int, choice, file), which section it lives in, the help text, whether it needs
root, how the value attaches to the flag (` `, `=`, or glued like `-PS22,80`),
and where it lands in the emitted command.

**Kinds:** `FLAG`, `TEXT`, `INT`, `CHOICE`, `FILE`, `EXCLUSIVE` (radio groups —
scan technique and host discovery are mutually exclusive sets).

**Two-way.** `parse_command()` maps a typed command back onto the catalogue, so
editing the command line drives the checkboxes. Anything it cannot map is kept
as a verbatim custom command and the field turns amber.

---

## 8. NSE script handling

- Names and categories come from `script.db` — one file read, instant.
- Descriptions, `@args` and `@usage` are lifted from the `.nse` Lua source on
  demand and cached, so start-up stays fast with 600+ scripts.
- Lua sources hard-wrap at ~75 columns; `_reflow()` rejoins those lines into
  paragraphs so they read properly in a resizable panel.
- Risk colouring: `safe`/`default`/`discovery` → green, `intrusive`/`vuln`/`auth`
  → amber, `brute`/`dos`/`exploit`/`fuzzer` → red. Selecting a red one asks for
  confirmation before the scan starts.

---

## 9. Storage

```
Linux    ~/.config/nmapgui/
Windows  %APPDATA%\NmapStudio\
macOS    ~/Library/Application Support/nmapgui/
```

| File | Contents |
|---|---|
| `history.db` | SQLite: title, target, command, config JSON, full XML, console output, timings, counts |
| `settings.json` | theme, accent colour, font size, recent targets, elevation helper |
| `profiles.json` | profiles you saved |

The whole XML is stored, which is what lets a past scan be reopened into a fully
working tab and diffed against a new one.

---

## 10. The design system

All of it comes from `design.py`.

**Concentric radii** — a surface's radius is the radius of what it contains plus
the padding between them:

```
control 7px  +  padding 3  =  panel 10px  +  padding 4  =  card 14px
```

**Spacing** is a 4px scale. **Type** is a five-step scale with an uppercase
eyebrow style that carries letter-spacing. **Motion** is asymmetric — entrances
200 ms, exits 130 ms — so dismissals never feel sluggish.

**Colour.** One accent carries the interface. Green, amber and red mean a *port
state* and nothing else. Every text colour clears WCAG AA against the surface it
sits on, in both themes — checked numerically, not by eye.

**Numbers** that update use tabular figures (`QFont.setFeature(QFont.Tag("tnum"))`)
so the countdown and counters do not jitter as digits change.

**Progressive disclosure.** Option rows are one line; the explanation for the
row under the pointer appears in a strip at the foot of the panel. Value editors
appear only when their option is switched on. The scan header is a single quiet
line until there is something to report.

**Theme switching is live.** Every widget shares one palette dict which is
mutated in place, then `restyle_tree()` walks the widget tree calling `restyle()`
on anything that styles itself. No restart.

**No image assets.** Icons, the progress ring and the topology map are drawn
with QPainter, so they stay sharp at any DPI and recolour with the theme.

---

## 11. Cross-platform behaviour

`platform_support.py` is the only module that asks what OS it is on.

| Concern | Linux / macOS | Windows |
|---|---|---|
| Find nmap | bundled copy → PATH → `/usr/bin` … | bundled copy → PATH → `C:\Program Files (x86)\Nmap` |
| Privileges | `geteuid() == 0` | `shell32.IsUserAnAdmin()` |
| Elevate | `pkexec`, `sudo`, `doas` | must be started as administrator |
| Pause | `SIGSTOP` / `SIGCONT` | not possible — the button is hidden |
| Console window | n/a | `CREATE_NO_WINDOW` |
| Config | `~/.config` / `Application Support` | `%APPDATA%` |
| Manual | `man nmap` | opens the online manual |

A **bundled nmap beside the app wins over everything else**, which is what makes
the Windows installer self-contained.

---

## 12. Privileges

Raw-socket options — `-sS`, `-sU`, `-O`, `--traceroute`, `-f`, `-D`, `--spoof-mac`
and friends — are marked `root=True` in the catalogue. The toolbar chip appears
only when the current command needs them.

On Linux the app offers to relaunch that scan through `pkexec` or `sudo`, or to
run unprivileged and let nmap fall back (a SYN scan quietly becomes a connect
scan). On Windows there is no after-the-fact elevation: it must be started as
administrator, and Npcap must be installed.

---

## 13. Building the packages

```bash
./packaging/build-deb.sh --bundled        # -> dist/nmap-studio-bundled_1.0_amd64.deb
./packaging/build-windows-installer.sh    # -> dist/NmapStudio-Setup.exe
./packaging/build-linux-binary.sh         # -> dist/nmap-studio (single file)
python3 packaging/make-icons.py           # regenerate the icon set
```

| Script | What it does |
|---|---|
| `build-deb.sh` | Debian package. `--bundled` embeds the frozen binary so only `nmap` is a dependency |
| `build-windows-installer.sh` | NSIS installer. Runs **on Linux** — no Windows machine needed |
| `fetch-windows-runtime.sh` | Downloads embeddable Python + PyQt6 wheels, trims unused Qt modules |
| `fetch-windows-nmap.sh` | Extracts nmap's Windows files from the official installer — **never Npcap** |
| `build-linux-binary.sh` | PyInstaller single-file build |
| `build-windows.bat` | Same, run on Windows, produces `NmapStudio.exe` |
| `install.sh` | Plain install/uninstall for non-Debian Linux |

**What ends up in the Windows installer** (46 MB compressed):

```
NmapStudio-Setup.exe
├── nmapgui\            the application
├── runtime\            Python 3.12 + PyQt6 + Qt 6   (140 MB on disk)
├── nmap\               nmap 7.99 + 613 NSE scripts   (32 MB)
├── launch.bat
├── icon.ico
└── uninstall.exe
```

**Npcap is deliberately excluded** — its licence forbids redistribution. The
build script asserts zero Npcap files in the bundle. See [NOTICE](../NOTICE.md)
for the full licensing position on nmap, Npcap and Qt.

---

## 14. Testing

```bash
python3 selftest.py            # parsing, commands, views, exports, live process
python3 selftest.py --scan     # plus a full scan of 127.0.0.1
```

It runs the real window off-screen (`QT_QPA_PLATFORM=offscreen`), so it needs no
display. Coverage: XML parsing including half-written documents, command build
and round-trip, the countdown helpers, progress scraping, the catalogues, all
four exporters, diffing, every result view, toasts, theme switching — and a real
nmap process through the pty backend, checking output arrives and the state
machine ends where it should.

> That last check exists because a lost import once broke live scanning while
> every other test still passed. Anything that only breaks in a real process
> needs a real process to catch it.

---

## 15. Extending it

**Add an nmap option** — one row in `optionsdata.py`. The UI, the command
builder and the command parser all pick it up:

```python
Opt("min_rate", "--min-rate", "Min packets / second", INT, "timing",
    "Send no slower than this.", placeholder="300")
```

**Add a scan profile** — one `Profile(...)` in the same file.

**Add a result view** — a widget with `refresh(result)` and `restyle()`, then one
line in `ScanTab`.

**Add an icon** — one branch in `icons.py` drawing on a 24×24 grid. Check it at
15 px: thin strokes and small details disappear at that size.

**Add an export format** — a function in `exporters.py` taking a `ScanResult`,
then one entry in the File → Export menu.

---

<div align="center">

Designed and built by **[oph](https://github.com/op-h)**

</div>
