"""Application entry point."""
from __future__ import annotations

import signal
import sys

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication

from .mainwindow import APP_NAME, MainWindow


USAGE = """Nmap Studio — a graphical front-end for nmap.

  nmap-studio                        start with an empty scan
  nmap-studio 10.0.0.0/24            start with the target filled in
  nmap-studio --open results.xml     open an existing nmap XML file

Everything else is done in the window: pick a profile or build the command
from the option panel, choose NSE scripts, and press Scan (Ctrl+Enter).
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "-h" in argv[1:] or "--help" in argv[1:]:
        print(USAGE)
        return 0

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("nmap-studio")
    app.setDesktopFileName("nmap-studio")

    from .icons import app_icon
    app.setWindowIcon(app_icon())

    window = MainWindow()

    # Honour command line arguments: a target, or --open file.xml
    args = argv[1:]
    if "--open" in args:
        index = args.index("--open")
        if index + 1 < len(args):
            from .parser import parse_xml_file
            path = args[index + 1]
            result = parse_xml_file(path)
            if result is not None:
                with open(path, errors="replace") as handle:
                    window.new_tab(path).load_result(handle.read(), "", path, result.args)
        args = args[:index] + args[index + 2:]
    targets = [a for a in args if not a.startswith("-")]
    if targets:
        window.target_input.setCurrentText(" ".join(targets))
        window.refresh_command()

    window.show()

    # Let Ctrl+C in the launching terminal close the window.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.start(400)
    timer.timeout.connect(lambda: None)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
