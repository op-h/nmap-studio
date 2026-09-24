#!/usr/bin/env python3
"""Headless self-test for Nmap Studio.

Builds the window offscreen, exercises the parts that are easy to break, and
optionally runs a real scan against 127.0.0.1.

    python3 selftest.py            # widgets, parsing, exports — no scanning
    python3 selftest.py --scan     # also runs a short scan of this machine
"""
from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer                                     # noqa: E402
from PyQt6.QtWidgets import QApplication                            # noqa: E402

from nmapgui.command import ScanConfig, parse_command               # noqa: E402
from nmapgui.exporters import (diff_results, diff_to_text, to_csv,   # noqa: E402
                               to_html, to_json, to_markdown)
from nmapgui.mainwindow import MainWindow                           # noqa: E402
from nmapgui.nse import load_catalogue                              # noqa: E402
from nmapgui.optionsdata import BUILTIN_PROFILES, OPTIONS           # noqa: E402
from nmapgui.parser import parse_xml_text, scrape_progress          # noqa: E402
from nmapgui.widgets.scanheader import fmt_clock, parse_duration    # noqa: E402

PASS, FAIL = "  ok  ", " FAIL "
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{PASS if condition else FAIL}] {name}" + (f"  - {detail}" if detail else ""))
    if not condition:
        failures.append(name)


SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap -sV 10.0.0.1" start="1700000000" version="7.99">
<host><status state="up" reason="echo-reply"/><address addr="10.0.0.1" addrtype="ipv4"/>
<hostnames><hostname name="router.lan" type="PTR"/></hostnames><ports>
<port protocol="tcp" portid="22"><state state="open" reason="syn-ack"/>
<service name="ssh" product="OpenSSH" version="8.9"/></port>
<port protocol="tcp" portid="80"><state state="open" reason="syn-ack"/>
<service name="http" product="nginx" version="1.22"/>
<script id="http-title" output="Home"/></port></ports>
<os><osmatch name="Linux 5.4" accuracy="96"/></os></host>
<runstats><finished elapsed="4.20" summary="done" exit="success"/>
<hosts up="1" down="0" total="1"/></runstats></nmaprun>"""


def main() -> int:
    app = QApplication([])

    print("\n--- parsing and command building ---")
    result = parse_xml_text(SAMPLE_XML)
    check("XML parses", result is not None and len(result.hosts) == 1)
    check("ports parsed", result.open_port_count == 2, f"{result.open_port_count} open")
    check("service banner", result.hosts[0].ports[0].service.banner == "OpenSSH 8.9")
    check("script output", "http-title" in result.hosts[0].ports[1].scripts)
    check("OS match", result.hosts[0].best_os == "Linux 5.4")
    check("half-written XML still parses",
          parse_xml_text(SAMPLE_XML[: len(SAMPLE_XML) // 2]) is not None)

    cfg = ScanConfig(targets="10.0.0.0/24", opts={"sS": True, "T": "4", "p": "1-1000"},
                     scripts=["http-title"], run_default_scripts=True)
    check("command preview",
          cfg.preview() == "nmap -sS -p 1-1000 -T4 -sC --script=http-title 10.0.0.0/24",
          cfg.preview())
    check("argv adds live stats and XML", "--stats-every" in cfg.argv("/tmp/x.xml"))
    check("root detection", cfg.needs_root() == ["-sS"])
    check("validation catches an empty target", bool(ScanConfig().validate()))

    back, _ = parse_command(cfg.preview())
    check("command round-trips into the builder",
          back is not None and back.opts.get("p") == "1-1000" and back.run_default_scripts)
    unknown, note = parse_command("nmap --not-a-real-flag 10.0.0.1")
    check("unknown flags fall back to a custom command", unknown is None, note)

    print("\n--- countdown helpers ---")
    check("clock formatting",
          [fmt_clock(x) for x in (None, 9, 61, 3600)] == ["--:--", "0:09", "1:01", "1:00:00"])
    check("duration parsing", parse_duration("0:02:03") == 123.0)
    prog = scrape_progress(
        "Stats: 0:00:05 elapsed; 0 hosts completed (1 up), 1 undergoing SYN Stealth Scan\n"
        "SYN Stealth Scan Timing: About 24.63% done; ETC: 15:02 (0:00:12 remaining)\n")
    check("progress scraped from nmap output",
          prog is not None and prog.percent == 24.63 and prog.remaining == "0:00:12"
          and prog.task == "SYN Stealth Scan")

    print("\n--- catalogues ---")
    check("option catalogue", len(OPTIONS) >= 100, f"{len(OPTIONS)} options")
    check("profiles", len(BUILTIN_PROFILES) >= 16, f"{len(BUILTIN_PROFILES)} profiles")
    scripts = load_catalogue()
    check("NSE catalogue", len(scripts) > 100, f"{len(scripts)} scripts")

    print("\n--- exports ---")
    for name, fn in (("csv", to_csv), ("html", to_html), ("json", to_json),
                     ("md", to_markdown)):
        try:
            check(f"export {name}", len(fn(result)) > 50)
        except Exception as exc:                                    # noqa: BLE001
            check(f"export {name}", False, repr(exc))
    report = diff_results(result, parse_xml_text(SAMPLE_XML.replace('portid="80"',
                                                                    'portid="8080"')))
    check("scan diff finds the change",
          "8080/tcp" in str(report["changed"]) and "80/tcp" in diff_to_text(report))

    print("\n--- window ---")
    window = MainWindow()
    window.resize(1500, 950)
    window.show()
    check("window built", window.isVisible())
    check("option rows built", len(window.builder.rows) == len(OPTIONS))
    check("script browser loaded", len(window.scripts_panel.catalogue) > 100)

    for index in range(1, window.profile_combo.count()):
        window.profile_combo.setCurrentIndex(index)
    check("every profile applies", bool(window.command_edit.text()))
    window.profile_combo.setCurrentIndex(0)
    window.builder.reset()

    window.target_input.setCurrentText("10.0.0.1")
    window.command_edit.setText("nmap -sU --top-ports 50 -T2 10.0.0.1")
    window._on_command_edited(window.command_edit.text())
    check("typed command drives the builder",
          window.builder.options().get("sU") is True
          and window.builder.options().get("top_ports") == "50")

    tab = window.current_tab()
    tab.load_result(SAMPLE_XML, "console text", "selftest", "nmap -sV 10.0.0.1", 4.2)
    check("results load into the tab", tab.ports.table.rowCount() == 2)
    check("hosts tree filled", tab.hosts.tree.topLevelItemCount() == 1)
    check("scripts tree filled", tab.scripts.tree.topLevelItemCount() == 1)
    check("topology drawn", len(tab.topology.scene.items()) > 2)
    check("countdown shows the total", tab.header.countdown.text() == "0:04",
          tab.header.countdown.text())

    for index in range(tab.tabs.count()):
        tab.tabs.setCurrentIndex(index)
        app.processEvents()
    check("every result view renders", True)

    for index in range(5):
        window.show_toast(f"self-test toast {index}", "good")
    app.processEvents()
    check("toasts are capped", 0 < len(window._toasts) <= MainWindow.MAX_TOASTS,
          f"{len(window._toasts)} on screen")

    for theme in ("light", "dark"):
        window.settings["theme"] = theme
        window.apply_theme()
    app.processEvents()
    check("theme switch survives", True)

    print("\n--- the scan process (this is what breaks silently) ---")
    from nmapgui.runner import ScanRunner
    from nmapgui.process import HAVE_PTY, have_winpty

    runner = ScanRunner()
    seen = {"chunks": [], "code": None, "states": []}
    runner.output_chunk.connect(seen["chunks"].append)
    runner.state_changed.connect(seen["states"].append)
    runner.finished.connect(lambda code, note: (seen.update(code=code), app.quit()))
    runner.start(ScanConfig(targets="127.0.0.1", opts={"sn": True}))
    QTimer.singleShot(45_000, app.quit)
    app.exec()

    output = "".join(seen["chunks"])
    check("the scan process starts and finishes", seen["code"] == 0, f"exit {seen['code']}")
    check("output comes back from the process", "Nmap done" in output,
          f"{len(output)} bytes")
    check("it ran on a pseudo-terminal" if (HAVE_PTY or have_winpty())
          else "it ran through QProcess", runner.using_pty or not HAVE_PTY)
    check("state went running -> idle", seen["states"][:1] == ["running"]
          and seen["states"][-1] == "idle", " -> ".join(seen["states"]))
    runner.cleanup()

    if "--scan" in sys.argv:
        print("\n--- live scan of 127.0.0.1 ---")
        window.command_edit.setText("nmap -sT -F --reason 127.0.0.1")
        window._on_command_edited(window.command_edit.text())
        window.run_scan()
        live = window.current_tab()
        state = {"done": False}

        def finished(_tab):
            state["done"] = True
            check("scan produced a result", live.result is not None)
            check("console output captured", "Nmap done" in live.output.plain_text())
            check("header reports a total", live.header.countdown_caption.text() == "total")
            app.quit()

        live.scan_finished.connect(finished)
        QTimer.singleShot(120_000, app.quit)
        app.exec()
        check("scan finished within the timeout", state["done"])
        live.runner.cleanup()

    print("\n" + "=" * 58)
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                               # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
