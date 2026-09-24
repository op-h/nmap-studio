"""Nmap Studio — the main window."""
from __future__ import annotations

import os
import shutil
import subprocess
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication, QKeySequence
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
                             QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QStatusBar,
                             QTabWidget, QToolBar, QVBoxLayout, QWidget)

from . import icons, storage
from .command import NMAP, ScanConfig, is_root, parse_command
from .design import HIT, RADIUS, SPACE, TYPE
from .platform_support import (IS_WINDOWS, can_pause, elevation_helpers,
                                elevation_hint, has_manpage, open_url)
from .exporters import diff_results, diff_to_text, to_csv, to_html, to_json, to_markdown
from .optionsdata import BUILTIN_PROFILES
from .parser import parse_xml_file, parse_xml_text
from .theme import palette_for, qt_palette, stylesheet
from .widgets.optionbuilder import OptionBuilder
from .widgets.scantab import ScanTab
from .widgets.scriptbrowser import ScriptBrowser
from .widgets.common import IconField, Toast, restyle_tree
from .widgets.sidebar import HistoryPanel, ProfilePanel

APP_NAME = "Nmap Studio"
VERSION = "1.0"
AUTHOR = "oph"
AUTHOR_URL = "https://github.com/op-h"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = storage.load_settings()
        self.pal = palette_for(self.settings["theme"], self.settings.get("accent"))
        self.recent_targets: list[str] = self.settings.get("recent_targets", [])
        self._syncing = False
        self._toasts: list = []

        self.setWindowTitle(APP_NAME)
        self.resize(1560, 950)
        self.setMinimumSize(1050, 680)
        self.setWindowIcon(icons.app_icon())

        self._build_toolbar()
        self._build_docks()
        self._build_central()
        self._build_statusbar()
        self._build_menu()
        self.apply_theme()

        self.new_tab()
        self.refresh_command()
        QTimer.singleShot(150, self._check_environment)

    # ==================================================================== ui
    def _build_toolbar(self) -> None:
        bar = QToolBar("Scan", self)
        bar.setMovable(False)
        bar.setFloatable(False)
        self.addToolBar(bar)

        self.target_input = QComboBox(self)
        self.target_input.setEditable(True)
        self.target_input.setMinimumWidth(340)
        self.target_input.setMinimumHeight(HIT["comfortable"])
        self.target_input.lineEdit().setPlaceholderText(
            "Target — host name, IP, range or CIDR")
        self.target_input.addItems(self.recent_targets)
        self.target_input.setCurrentText("")
        self.target_input.setToolTip(
            "Hosts, ranges, CIDR blocks or names — separated by spaces")
        self.target_input.currentTextChanged.connect(self.refresh_command)
        self.target_input.lineEdit().returnPressed.connect(self.run_scan)
        bar.addWidget(self.target_input)

        self.profile_combo = QComboBox(self)
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.setMinimumHeight(HIT["comfortable"])
        self.profile_combo.addItem("Custom", None)
        for profile in BUILTIN_PROFILES:
            self.profile_combo.addItem(profile.name, profile.name)
            self.profile_combo.setItemData(self.profile_combo.count() - 1,
                                           profile.description, Qt.ItemDataRole.ToolTipRole)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_combo)
        bar.addWidget(self.profile_combo)

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)

        self.root_chip = QLabel(self)
        self.root_chip.setToolTip("Privilege level this command needs")
        self.root_chip.setVisible(False)
        bar.addWidget(self.root_chip)

        # Stop only exists while something is running — no permanently dead button.
        self.stop_button = QPushButton("  Stop", self)
        self.stop_button.setProperty("danger", "true")
        self.stop_button.setIcon(icons.icon("stop", self.pal["closed"], 15))
        self.stop_button.setMinimumHeight(HIT["comfortable"])
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_scan)
        bar.addWidget(self.stop_button)

        self.scan_button = QPushButton("  Scan", self)
        self.scan_button.setProperty("accent", "true")
        self.scan_button.setIcon(icons.icon("play", self.pal["accent_text"], 15))
        self.scan_button.setMinimumHeight(HIT["comfortable"])
        self.scan_button.setMinimumWidth(96)
        self.scan_button.setToolTip("Run this scan  (Ctrl+Enter)")
        self.scan_button.clicked.connect(self.run_scan)
        bar.addWidget(self.scan_button)

        # ---- second row: the command itself
        cmd_bar = QToolBar("Command", self)
        cmd_bar.setMovable(False)
        cmd_bar.setFloatable(False)
        self.addToolBarBreak()
        self.addToolBar(cmd_bar)

        self.command_field = IconField("terminal", self.pal, self, mono=True)
        self.command_edit = self.command_field.edit
        self.command_edit.setPlaceholderText("nmap …")
        self.command_edit.setToolTip(
            "Editable. Type any nmap command and the option panel follows along;\n"
            "anything the builder does not recognise is passed to nmap verbatim.")
        self.command_edit.textEdited.connect(self._on_command_edited)
        self.command_edit.returnPressed.connect(self.run_scan)
        cmd_bar.addWidget(self.command_field)

        self._chrome_buttons = []
        for name, tip, slot in (
                ("copy", "Copy the command",
                 lambda: self._copy(self.command_edit.text(), "Command copied")),
                ("refresh", "Rebuild the command from the option panel",
                 self.refresh_command)):
            button = QPushButton(self)
            self._chrome_buttons.append((button, name))
            button.setIcon(icons.icon(name, self.pal["dim"], 15))
            button.setToolTip(tip)
            button.setProperty("flat", "true")
            button.setFixedSize(HIT["comfortable"], HIT["comfortable"])
            button.clicked.connect(slot)
            cmd_bar.addWidget(button)

    def _build_docks(self) -> None:
        from PyQt6.QtWidgets import QDockWidget

        self.side_tabs = QTabWidget(self)
        self.side_tabs.setDocumentMode(True)

        self.builder = OptionBuilder(self.pal, self)
        self.builder.changed.connect(self.refresh_command)
        self.scripts_panel = ScriptBrowser(self.pal, self)
        self.scripts_panel.changed.connect(self.refresh_command)
        self.profiles_panel = ProfilePanel(self.pal, self)
        self.profiles_panel.profile_chosen.connect(self.apply_profile)
        self.profiles_panel.save_requested.connect(self.save_profile)
        self.history_panel = HistoryPanel(self.pal, self)
        self.history_panel.open_requested.connect(self.open_history_scan)
        self.history_panel.compare_requested.connect(self.compare_scans)

        self.side_tabs.addTab(self.builder, icons.icon("sliders", self.pal["dim"], 16), "Options")
        self.side_tabs.addTab(self.scripts_panel, icons.icon("script", self.pal["dim"], 16),
                              "NSE Scripts")
        self.side_tabs.addTab(self.profiles_panel, icons.icon("star", self.pal["dim"], 16),
                              "Profiles")
        self.side_tabs.addTab(self.history_panel, icons.icon("history", self.pal["dim"], 16),
                              "History")

        self.dock = QDockWidget("Scan builder", self)
        self.dock.setTitleBarWidget(QWidget(self))     # the tabs are the title
        self.dock.setWidget(self.side_tabs)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                              QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.dock.setMinimumWidth(400)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def _build_central(self) -> None:
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(lambda *_: self._sync_buttons())

        corner = QPushButton(self)
        corner.setIcon(icons.icon("plus", self.pal["dim"], 16))
        corner.setToolTip("New scan tab (Ctrl+T)")
        corner.setProperty("flat", "true")
        corner.setFixedWidth(34)
        corner.clicked.connect(lambda: self.new_tab())
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.setCentralWidget(self.tabs)

    def _build_statusbar(self) -> None:
        status = QStatusBar(self)
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        self.status_credit = QLabel(self)
        self.status_credit.setOpenExternalLinks(True)
        self.status_credit.setToolTip(f"Designed and built by {AUTHOR} — {AUTHOR_URL}")
        self.status_nmap = QLabel(self)
        self.status_priv = QLabel(self)
        self.status_scans = QLabel(self)
        for index, widget in enumerate((self.status_credit, self.status_nmap,
                                        self.status_priv, self.status_scans)):
            if index:
                separator = QFrame(self)
                separator.setProperty("role", "vsep")
                separator.setFixedSize(1, 14)
                status.addPermanentWidget(separator)
            status.addPermanentWidget(widget)
        status.showMessage("Ready.")

    def _build_menu(self) -> None:
        pal = self.pal
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        self._act(file_menu, "New scan tab", "Ctrl+T", lambda: self.new_tab(), "plus")
        self._act(file_menu, "Close scan tab", "Ctrl+W",
                  lambda: self.close_tab(self.tabs.currentIndex()), "close")
        file_menu.addSeparator()
        self._act(file_menu, "Open nmap XML…", "Ctrl+O", self.open_xml, "folder")
        export = file_menu.addMenu("Export results")
        export.setIcon(icons.icon("export", pal["dim"], 16))
        for label, kind in (("HTML report…", "html"), ("CSV…", "csv"), ("JSON…", "json"),
                            ("Markdown…", "md"), ("nmap XML…", "xml"),
                            ("Console text…", "txt")):
            export.addAction(label, lambda _=False, k=kind: self.export(k))
        file_menu.addSeparator()
        self._act(file_menu, "Save scan to history", "Ctrl+S", self.save_current_to_history,
                  "save")
        file_menu.addSeparator()
        self._act(file_menu, "Quit", "Ctrl+Q", self.close, "close")

        scan_menu = menu.addMenu("&Scan")
        self._act(scan_menu, "Run scan", "Ctrl+Return", self.run_scan, "play")
        self._act(scan_menu, "Run in a new tab", "Ctrl+Shift+Return",
                  lambda: self.run_scan(new_tab=True), "plus")
        self._act(scan_menu, "Stop scan", "Ctrl+.", self.stop_scan, "stop")
        pause_action = self._act(scan_menu, "Pause / resume", "Ctrl+P",
                                 self.toggle_pause, "pause")
        pause_action.setEnabled(can_pause())
        if not can_pause():
            pause_action.setToolTip("Windows has no way to suspend a running process")
        scan_menu.addSeparator()
        self._act(scan_menu, "Repeat this scan", "Ctrl+R", self.repeat_scan, "refresh")
        self._act(scan_menu, "Compare with another scan…", "", self.compare_dialog, "compare")
        scan_menu.addSeparator()
        keys = scan_menu.addMenu("Send key to running nmap")
        keys.setToolTipsVisible(True)
        for label, key in (("Increase verbosity (v)", "v"), ("Decrease verbosity (V)", "V"),
                           ("Increase debugging (d)", "d"), ("Decrease debugging (D)", "D"),
                           ("Toggle packet trace (p)", "p"), ("Print status (Enter)", "\n")):
            keys.addAction(label, lambda _=False, k=key: self.send_key(k))

        view_menu = menu.addMenu("&View")
        self.theme_action = QAction("Light theme", self, checkable=True)
        self.theme_action.setChecked(self.settings["theme"] == "light")
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)
        self._act(view_menu, "Accent colour…", "", self.choose_accent, "settings")
        view_menu.addSeparator()
        self._act(view_menu, "Toggle scan builder", "Ctrl+B",
                  lambda: self.dock.setVisible(not self.dock.isVisible()), "sliders")
        self._act(view_menu, "Expand all option sections", "",
                  lambda: self.builder.expand_all(True), "chevron-down")
        self._act(view_menu, "Collapse all option sections", "",
                  lambda: self.builder.expand_all(False), "chevron-right")
        view_menu.addSeparator()
        self._act(view_menu, "Bigger text", "Ctrl+=", lambda: self.bump_font(1), "plus")
        self._act(view_menu, "Smaller text", "Ctrl+-", lambda: self.bump_font(-1), "close")

        tools_menu = menu.addMenu("&Tools")
        self._act(tools_menu, "Network interfaces (--iflist)", "", self.show_interfaces,
                  "network")
        self._act(tools_menu, "nmap version and features", "", self.show_nmap_version, "info")
        self._act(tools_menu, "Update NSE script database", "", self.update_script_db, "refresh")
        self._act(tools_menu, "Reload NSE catalogue", "", self.scripts_panel.reload, "script")
        tools_menu.addSeparator()
        self._act(tools_menu, "Clear all options", "", self.builder.reset, "trash")

        help_menu = menu.addMenu("&Help")
        self._act(help_menu, "Keyboard shortcuts", "F1", self.show_shortcuts, "key")
        self._act(help_menu, "nmap manual (man page)", "", self.show_manpage, "script")
        help_menu.addSeparator()
        self._act(help_menu, f"{AUTHOR} on GitHub", "",
                  lambda: open_url(AUTHOR_URL), "star")
        self._act(help_menu, f"About {APP_NAME}", "", self.show_about, "info")

    def _act(self, menu, text: str, shortcut: str, slot, icon_name: str = "") -> QAction:
        action = QAction(text, self)
        if icon_name:
            action.setIcon(icons.icon(icon_name, self.pal["dim"], 16))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ================================================================ config
    MAX_TOASTS = 3

    def show_toast(self, message: str, kind: str = "info") -> None:
        """Transient feedback that never steals focus or blocks the scan."""
        # Keep the stack short: a burst of messages should not wallpaper the window.
        while len(self._toasts) >= self.MAX_TOASTS:
            self._toasts.pop(0).deleteLater()
        toast = Toast(message, self.pal, kind, self)
        toast.dismissed.connect(lambda t=toast: self._drop_toast(t))
        self._toasts.append(toast)
        self._place_toasts()
        toast.show()
        toast.raise_()

    def _drop_toast(self, toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._place_toasts()

    def _place_toasts(self) -> None:
        margin = SPACE["xl"]
        bottom = self.height() - self.statusBar().height() - margin
        for toast in reversed(self._toasts):
            bottom -= toast.height()
            toast.move(self.width() - toast.width() - margin, bottom)
            bottom -= SPACE["md"]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_toasts()

    def current_tab(self) -> ScanTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, ScanTab) else None

    def build_config(self) -> ScanConfig:
        config = ScanConfig(
            targets=self.target_input.currentText().strip(),
            opts=self.builder.options(),
            scripts=self.scripts_panel.scripts(),
            script_args=self.scripts_panel.args_text(),
        )
        typed = self.command_edit.text().strip()
        if typed and typed != config.preview():
            config.custom_command = typed
        return config

    def refresh_command(self, *_args) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            config = ScanConfig(
                targets=self.target_input.currentText().strip(),
                opts=self.builder.options(),
                scripts=self.scripts_panel.scripts(),
                script_args=self.scripts_panel.args_text())
            self.command_edit.setText(config.preview())
            self._set_custom_command(False)
            self._update_root_chip(config)
        finally:
            self._syncing = False

    def _on_command_edited(self, text: str) -> None:
        """Typed commands feed straight back into the option panel when possible."""
        if self._syncing:
            return
        parsed, note = parse_command(text)
        self._syncing = True
        try:
            if parsed is None:
                self._set_custom_command(True)
                self.command_edit.setToolTip(
                    f"Passed to nmap verbatim — the builder does not recognise this "
                    f"({note}).")
                self.statusBar().showMessage(f"Custom command: {note}", 4000)
            else:
                self._set_custom_command(False)
                self.builder.set_options(parsed.opts)
                self.scripts_panel.set_state(parsed.scripts, parsed.script_args)
                if parsed.run_default_scripts and "default" not in parsed.scripts:
                    self.scripts_panel.set_state(
                        sorted(set(parsed.scripts) | {"default"}), parsed.script_args)
                if parsed.targets:
                    self.target_input.setCurrentText(parsed.targets)
                self._update_root_chip(parsed)
        finally:
            self._syncing = False

    def _set_custom_command(self, custom: bool) -> None:
        self.command_field.setProperty("custom", "true" if custom else "false")
        self.command_field.style().unpolish(self.command_field)
        self.command_field.style().polish(self.command_field)

    def _copy(self, text: str, note: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.show_toast(note, "info")

    def _update_root_chip(self, config: ScanConfig) -> None:
        needs = config.needs_root()
        self.root_chip.setVisible(bool(needs) or is_root())
        if is_root():
            text = "ADMINISTRATOR" if IS_WINDOWS else "ROOT"
            colour = self.pal["open"]
            tip = "Full privileges — every option is available."
        elif needs:
            text = ("NEEDS ADMIN  " if IS_WINDOWS else "NEEDS ROOT  ") + " ".join(needs)
            colour = self.pal["filtered"]
            tip = ("These options need raw sockets. " + elevation_hint()
                   if IS_WINDOWS or not elevation_helpers() else
                   "These options need raw sockets. Nmap Studio will offer to run "
                   "the scan through " + elevation_helpers()[0] + ".")
        else:
            text, colour = "UNPRIVILEGED", self.pal["dim"]
            tip = "Nothing selected needs raw sockets."
        self.root_chip.setText(text)
        self.root_chip.setToolTip(tip)
        self.root_chip.setStyleSheet(
            f"color:{colour};background:{self.pal['surface2']};"
            f"border:1px solid {self.pal['line']};border-radius:{RADIUS['control']}px;"
            f"padding:5px {SPACE['lg']}px;margin-right:{SPACE['md']}px;"
            f"font-size:{TYPE['micro']}px;font-weight:700;")

    # ================================================================== tabs
    def new_tab(self, title: str = "New scan") -> ScanTab:
        tab = ScanTab(self.pal, self.settings.get("mono_size", 10), self)
        tab.state_changed.connect(lambda *_: self._sync_buttons())
        tab.scan_finished.connect(self._on_scan_finished)
        tab.title_changed.connect(lambda text, t=tab: self._retitle(t, text))
        tab.notify.connect(self.show_toast)
        index = self.tabs.addTab(tab, icons.icon("terminal", self.pal["dim"], 15), title)
        self.tabs.setCurrentIndex(index)
        return tab

    def _retitle(self, tab: ScanTab, title: str) -> None:
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.setTabText(index, title)

    def close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if not isinstance(widget, ScanTab):
            return
        if widget.is_running():
            confirm = QMessageBox.question(
                self, "Scan running",
                "This tab is still scanning. Stop it and close the tab?")
            if confirm != QMessageBox.StandardButton.Yes:
                return
            widget.stop()
        widget.runner.cleanup()
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_tab()

    def _sync_buttons(self) -> None:
        tab = self.current_tab()
        running = bool(tab and tab.is_running())
        self.stop_button.setVisible(running)
        self.scan_button.setText("  Scan in new tab" if running else "  Scan")
        active = sum(1 for i in range(self.tabs.count())
                     if isinstance(self.tabs.widget(i), ScanTab)
                     and self.tabs.widget(i).is_running())
        self.status_scans.setText(
            f"{active} running · {self.tabs.count()} tab{'' if self.tabs.count() == 1 else 's'}")
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, ScanTab):
                self.tabs.setTabIcon(index, icons.icon(
                    "play" if widget.is_running() else "terminal",
                    self.pal["accent"] if widget.is_running() else self.pal["dim"], 15))

    # =================================================================== run
    def run_scan(self, new_tab: bool = False) -> None:
        config = self.build_config()
        problems = config.validate()
        if problems:
            QMessageBox.warning(self, "Check the scan", "\n\n".join(problems))
            return

        risky = self.scripts_panel.risky_selection()
        if risky and self.settings.get("confirm_risky_scripts", True):
            confirm = QMessageBox.warning(
                self, "Intrusive scripts selected",
                "These scripts can disrupt, brute-force or exploit the target:\n\n"
                + ", ".join(risky) +
                "\n\nOnly run them against systems you are authorised to test.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if confirm != QMessageBox.StandardButton.Yes:
                return

        elevate = ""
        needs = config.needs_root()
        if needs and not is_root():
            elevate = self._ask_elevation(needs)
            if elevate is None:
                return

        tab = self.current_tab()
        if new_tab or tab is None or tab.is_running():
            tab = self.new_tab()
        tab.start(config, elevate)

        target = config.targets.strip()
        if target and target not in self.recent_targets:
            self.recent_targets.insert(0, target)
            self.recent_targets = self.recent_targets[:25]
            self.target_input.blockSignals(True)
            self.target_input.clear()
            self.target_input.addItems(self.recent_targets)
            self.target_input.setCurrentText(target)
            self.target_input.blockSignals(False)
        self._sync_buttons()
        self.statusBar().showMessage(f"Scanning {target or 'targets from file'}…", 5000)

    def _ask_elevation(self, needs: list[str]) -> str | None:
        """Offer to raise privileges. Returns a helper name, "" for unprivileged,
        or None if the person cancelled."""
        helpers = [h for h in elevation_helpers() if h != "uac"]
        preferred = self.settings.get("elevate", "pkexec")
        helper = preferred if preferred in helpers else (helpers[0] if helpers else "")

        box = QMessageBox(self)
        box.setWindowTitle("Privileges required")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("This scan uses options that need raw sockets:\n\n  "
                    + "  ".join(needs))
        box.setInformativeText(
            "Run it with elevated privileges, or let nmap fall back to what it can "
            "do as your user — a SYN scan quietly becomes a connect scan and OS "
            "detection is skipped.\n\n" + ("" if helper else elevation_hint()))

        elevate_btn = (box.addButton(f"Run with {helper}",
                                     QMessageBox.ButtonRole.AcceptRole)
                       if helper else None)
        plain_btn = box.addButton("Run unprivileged", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_btn:
            return None
        if elevate_btn is not None and clicked is elevate_btn:
            return helper
        return "" if clicked is plain_btn else None

    def stop_scan(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.stop()

    def toggle_pause(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.toggle_pause()

    def send_key(self, key: str) -> None:
        tab = self.current_tab()
        if tab and tab.is_running():
            tab.runner.send_key(key)
            self.show_toast(f"Sent “{key.strip() or 'Enter'}” to the running nmap", "info")

    def repeat_scan(self) -> None:
        tab = self.current_tab()
        if tab and tab.config:
            self.apply_config(tab.config)
            self.run_scan(new_tab=True)

    def _on_scan_finished(self, tab: ScanTab) -> None:
        self._sync_buttons()
        if self.settings.get("autosave_history", True):
            self._store(tab)
            self.history_panel.reload()
        result = tab.result
        if result:
            self.statusBar().showMessage(
                f"{tab.title}: {result.hosts_up} hosts up, {result.open_port_count} open "
                f"ports in {result.elapsed or '?'}s", 8000)

    def _store(self, tab: ScanTab) -> int | None:
        if tab.config is None:
            return None
        result = tab.result
        scan_id = storage.save_scan(
            title=tab.title, target=tab.config.targets, command=tab.config.preview(),
            config=tab.config.to_dict(), xml=tab.runner.xml_text(),
            output=tab.output.plain_text(), started=tab.started_at or time.time(),
            duration=tab.runner.elapsed,
            hosts_up=result.hosts_up if result else 0,
            hosts_total=result.hosts_total if result else 0,
            open_ports=result.open_port_count if result else 0,
            status="finished" if result and result.complete else "partial")
        tab.saved_id = scan_id
        return scan_id

    def save_current_to_history(self) -> None:
        tab = self.current_tab()
        if tab is None or tab.config is None:
            QMessageBox.information(self, "Nothing to save", "Run a scan first.")
            return
        self._store(tab)
        self.history_panel.reload()
        self.show_toast("Saved to history", "good")

    # =============================================================== profiles
    def apply_profile(self, data: dict) -> None:
        self._syncing = True
        try:
            self.builder.set_options(data.get("opts", {}))
            self.scripts_panel.set_state(data.get("scripts", []), data.get("script_args", ""))
        finally:
            self._syncing = False
        self.refresh_command()
        index = self.profile_combo.findData(data.get("name"))
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self.profile_combo.blockSignals(False)
        self.show_toast(f"Profile applied — {data['name']}", "info")

    def _on_profile_combo(self, index: int) -> None:
        name = self.profile_combo.itemData(index)
        if not name:
            return
        for profile in BUILTIN_PROFILES:
            if profile.name == name:
                self.apply_profile({"name": profile.name, "description": profile.description,
                                    "opts": dict(profile.opts), "scripts": list(profile.scripts),
                                    "script_args": profile.script_args})
                return

    def apply_config(self, config: ScanConfig) -> None:
        self._syncing = True
        try:
            self.target_input.setCurrentText(config.targets)
            self.builder.set_options(config.opts)
            self.scripts_panel.set_state(config.scripts, config.script_args)
        finally:
            self._syncing = False
        if config.custom_command:
            self.command_edit.setText(config.custom_command)
        else:
            self.refresh_command()

    def save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok or not name.strip():
            return
        description, _ = QInputDialog.getText(self, "Save profile",
                                              "One-line description (optional):")
        self.profiles_panel.add_user_profile({
            "name": name.strip(), "description": description.strip(),
            "opts": self.builder.options(), "scripts": self.scripts_panel.scripts(),
            "script_args": self.scripts_panel.args_text(), "builtin": False})
        self.show_toast(f"Saved profile “{name.strip()}”", "good")

    # ================================================================ history
    def open_history_scan(self, scan_id: int) -> None:
        data = storage.load_scan(scan_id)
        if data is None:
            return
        tab = self.new_tab(data["title"])
        tab.load_result(data.get("xml") or "", data.get("output") or "",
                        data["title"], data.get("command") or "")
        tab.saved_id = scan_id
        config = data.get("config") or {}
        if config:
            tab.config = ScanConfig.from_dict(config)
            self.apply_config(tab.config)

    def compare_scans(self, first_id: int, second_id: int) -> None:
        a, b = storage.load_scan(first_id), storage.load_scan(second_id)
        if not a or not b:
            return
        old = parse_xml_text(a.get("xml") or "")
        new = parse_xml_text(b.get("xml") or "")
        if old is None or new is None:
            QMessageBox.information(self, "Compare scans",
                                    "One of those scans has no stored XML to compare.")
            return
        if a["started"] > b["started"]:
            a, b, old, new = b, a, new, old
        text = diff_to_text(diff_results(old, new),
                            f"{a['title']} ({time.strftime('%Y-%m-%d %H:%M', time.localtime(a['started']))})",
                            f"{b['title']} ({time.strftime('%Y-%m-%d %H:%M', time.localtime(b['started']))})")
        self._text_dialog("Scan comparison", text, 820, 560)

    def compare_dialog(self) -> None:
        self.side_tabs.setCurrentWidget(self.history_panel)
        QMessageBox.information(
            self, "Compare scans",
            "Pick exactly two scans in the History panel (Ctrl+click), then press "
            "“Compare two”.")

    # ================================================================ import
    def open_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open nmap XML output", "",
                                              "nmap XML (*.xml);;All files (*)")
        if not path:
            return
        result = parse_xml_file(path)
        if result is None:
            QMessageBox.warning(self, "Cannot read that file",
                                "That does not look like nmap XML output.")
            return
        with open(path, errors="replace") as handle:
            xml = handle.read()
        tab = self.new_tab(os.path.basename(path))
        tab.load_result(xml, "", os.path.basename(path), result.args)
        self.show_toast(
            f"Loaded {len(result.hosts)} hosts from {os.path.basename(path)}", "good")

    def export(self, kind: str) -> None:
        tab = self.current_tab()
        if tab is None or (tab.result is None and kind not in ("txt",)):
            QMessageBox.information(self, "Nothing to export",
                                    "Run or open a scan first.")
            return
        filters = {"html": "HTML report (*.html)", "csv": "CSV (*.csv)",
                   "json": "JSON (*.json)", "md": "Markdown (*.md)",
                   "xml": "nmap XML (*.xml)", "txt": "Text (*.txt)"}
        default = f"{tab.title.replace('/', '_').replace(' ', '_')}.{kind}"
        path, _ = QFileDialog.getSaveFileName(self, f"Export as {kind.upper()}", default,
                                              filters[kind])
        if not path:
            return
        if kind == "html":
            data = to_html(tab.result, f"nmap — {tab.title}")
        elif kind == "csv":
            data = to_csv(tab.result)
        elif kind == "json":
            data = to_json(tab.result)
        elif kind == "md":
            data = to_markdown(tab.result)
        elif kind == "xml":
            data = tab.xml_view.plain_text() or tab.runner.xml_text()
        else:
            data = tab.output.plain_text()
        try:
            with open(path, "w") as handle:
                handle.write(data)
        except OSError as exc:
            QMessageBox.critical(self, "Could not write the file", str(exc))
            return
        self.show_toast(f"Exported to {os.path.basename(path)}", "good")

    # ================================================================= tools
    def show_interfaces(self) -> None:
        self._run_tool([NMAP, "--iflist"], "Network interfaces and routes")

    def show_nmap_version(self) -> None:
        self._run_tool([NMAP, "--version"], "nmap version")

    def show_manpage(self) -> None:
        if has_manpage():
            self._run_tool(["man", "nmap"], "nmap manual",
                           env={**os.environ, "MANPAGER": "cat", "PAGER": "cat",
                                "MANWIDTH": "100"})
        else:
            open_url("https://nmap.org/book/man.html")
            self.show_toast("Opened the nmap manual in your browser", "info")

    def update_script_db(self) -> None:
        confirm = QMessageBox.question(
            self, "Update script database",
            "Run 'nmap --script-updatedb'? This rebuilds the NSE index and usually "
            "needs root.")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        argv = [NMAP, "--script-updatedb"]
        helpers = [h for h in elevation_helpers() if h != "uac"]
        if not is_root() and helpers:
            from .command import elevated_argv
            argv = elevated_argv(argv, helpers[0])
        self._run_tool(argv, "Update NSE database")
        self.scripts_panel.reload()

    def _run_tool(self, argv: list[str], title: str, env=None) -> None:
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)
            text = (proc.stdout or "") + (proc.stderr or "")
        except (OSError, subprocess.SubprocessError) as exc:
            text = f"Could not run {' '.join(argv)}:\n{exc}"
        self._text_dialog(title, text or "(no output)", 900, 620)

    def _text_dialog(self, title: str, text: str, width: int, height: int) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(width, height)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(dialog)
        view.setPlainText(text)
        view.setReadOnly(True)
        view.setProperty("mono", "true")
        view.setStyleSheet(
            f"QPlainTextEdit{{font-family:monospace;background:{self.pal['term_bg']};"
            f"border:1px solid {self.pal['line']};border-radius:8px;padding:10px;}}")
        layout.addWidget(view)
        buttons = QHBoxLayout()
        copy = QPushButton("Copy", dialog)
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        buttons.addWidget(copy)
        buttons.addStretch(1)
        close = QPushButton("Close", dialog)
        close.setProperty("accent", "true")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    # ================================================================= theme
    def apply_theme(self) -> None:
        """Repaint the whole window for the current theme, with no restart.

        Every widget holds a reference to this one palette dict, so it is
        mutated in place rather than replaced; then each widget that styles
        itself inline re-applies that styling through its restyle() hook.
        """
        app = QApplication.instance()
        fresh = palette_for(self.settings["theme"], self.settings.get("accent"))
        self.pal.clear()
        self.pal.update(fresh)

        app.setPalette(qt_palette(self.pal))
        app.setStyleSheet(stylesheet(self.pal, self.settings.get("font_size", 10),
                                     self.settings.get("mono_size", 10)))
        icons.clear_cache()          # icons are tinted, so the cache is now stale
        restyle_tree(self)
        self._restyle_chrome()
        self._sync_buttons()

    def _restyle_chrome(self) -> None:
        """The bits the main window styles itself: toolbar icons and status chips."""
        pal = self.pal
        self.scan_button.setIcon(icons.icon("play", pal["accent_text"], 15))
        self.stop_button.setIcon(icons.icon("stop", pal["closed"], 15))
        for button, name in self._chrome_buttons:
            button.setIcon(icons.icon(name, pal["dim"], 15))
        for index in range(self.side_tabs.count()):
            self.side_tabs.setTabIcon(index, icons.icon(
                ("sliders", "script", "star", "history")[index], pal["dim"], 16))
        for label in (self.status_nmap, self.status_priv, self.status_scans):
            label.setStyleSheet(f"color:{pal['dim']};")
        self.status_credit.setText(
            f'Designed by <a href="{AUTHOR_URL}" '
            f'style="color:{pal["accent"]};text-decoration:none;">{AUTHOR}</a>')
        self.status_credit.setStyleSheet(f"color:{pal['faint']};")
        self.status_nmap.setText(f"nmap {_nmap_version()}")
        self.status_priv.setText("root" if is_root() else "unprivileged")
        self.status_priv.setStyleSheet(
            f"color:{pal['open'] if is_root() else pal['dim']};")
        self.refresh_command()

    def toggle_theme(self) -> None:
        self.settings["theme"] = "light" if self.theme_action.isChecked() else "dark"
        storage.save_settings(self.settings)
        self.apply_theme()
        self.show_toast(f"{self.settings['theme'].capitalize()} theme applied", "info")

    def choose_accent(self) -> None:
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        colour = QColorDialog.getColor(QColor(self.pal["accent"]), self, "Accent colour")
        if colour.isValid():
            self.settings["accent"] = colour.name()
            storage.save_settings(self.settings)
            self.apply_theme()

    def bump_font(self, delta: int) -> None:
        self.settings["font_size"] = max(7, min(18, self.settings.get("font_size", 10) + delta))
        self.settings["mono_size"] = max(7, min(18, self.settings.get("mono_size", 10) + delta))
        storage.save_settings(self.settings)
        self.apply_theme()

    # ================================================================== help
    def show_shortcuts(self) -> None:
        self._text_dialog("Keyboard shortcuts", """
  Ctrl+Enter          Run the scan
  Ctrl+Shift+Enter    Run it in a new tab
  Ctrl+.              Stop the running scan
  Ctrl+P              Pause / resume the running scan
  Ctrl+R              Repeat the current scan in a new tab
  Ctrl+T / Ctrl+W     New scan tab / close scan tab
  Ctrl+O              Open an nmap XML file
  Ctrl+S              Save the current scan to history
  Ctrl+B              Show or hide the scan builder panel
  Ctrl+= / Ctrl+-     Bigger / smaller text
  F1                  This list

  In the output pane: type in the find box, Enter for the next match.
  While a scan runs: Scan -> Send key, for nmap's own runtime keys
  (v/V verbosity, d/D debugging, p packet trace, Enter for a status line).
""".strip("\n"), 660, 430)

    def show_about(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        box.setIconPixmap(icons.app_icon().pixmap(72, 72))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"""
<h3 style="margin-bottom:2px;">{APP_NAME} {VERSION}</h3>
<p style="color:{self.pal['dim']};margin-top:0;">
Designed and built by <b>{AUTHOR}</b> —
<a href="{AUTHOR_URL}" style="color:{self.pal['accent']};">{AUTHOR_URL}</a></p>
<p>A full graphical front-end for nmap: every scan technique, timing control,
evasion option and NSE script, with live results, a countdown to the finish,
a topology map, scan history and exportable reports.</p>
<p style="color:{self.pal['dim']};">Built with PyQt6. nmap itself is by Gordon
Lyon and the Nmap project — this is a front-end for it, not a fork of it.</p>
<p style="color:{self.pal['dim']};">Scan only hosts you own or have written
permission to test.</p>
""")
        box.exec()

    # =============================================================== lifecycle
    def _check_environment(self) -> None:
        from .command import nmap_available
        if not nmap_available():
            QMessageBox.critical(
                self, "nmap not found",
                "Nmap Studio needs nmap itself, and could not find it.\n\n"
                + ("Install it from https://nmap.org/download.html and tick "
                   "“Add Nmap to PATH” during setup."
                   if IS_WINDOWS else
                   "Install it with your package manager, for example:\n"
                   "    sudo apt install nmap"))
            return
        if not is_root():
            self.statusBar().showMessage(
                "Running unprivileged — SYN scan, OS detection and traceroute will ask "
                "for elevation when you use them.", 9000)

    def closeEvent(self, event) -> None:
        running = [i for i in range(self.tabs.count())
                   if isinstance(self.tabs.widget(i), ScanTab)
                   and self.tabs.widget(i).is_running()]
        if running:
            confirm = QMessageBox.question(
                self, "Scans still running",
                f"{len(running)} scan(s) are still running. Stop them and quit?")
            if confirm != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, ScanTab):
                if widget.is_running():
                    widget.stop()
                widget.runner.cleanup()
        self.settings["recent_targets"] = self.recent_targets
        storage.save_settings(self.settings)
        event.accept()


def _label(text: str, pal: dict, gap=(0, 0, 0, 0)) -> QLabel:
    """A toolbar caption. Uppercase micro type, so it never competes with input."""
    label = QLabel(text.upper())
    label.setContentsMargins(*gap)
    label.setStyleSheet(
        f"color:{pal['faint']};font-size:{TYPE['micro']}px;font-weight:700;")
    return label


def _nmap_version() -> str:
    try:
        proc = subprocess.run([NMAP, "--version"], capture_output=True, text=True, timeout=5)
        first = proc.stdout.splitlines()[0] if proc.stdout else ""
        return first.replace("Nmap version ", "").split(" (")[0] or "unknown"
    except (OSError, subprocess.SubprocessError, IndexError):
        return "not found"
