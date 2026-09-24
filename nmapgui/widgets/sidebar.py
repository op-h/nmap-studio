"""Profile library and scan history panels."""
from __future__ import annotations

import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
                             QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from .. import icons, storage
from ..design import HIT, SPACE, TYPE
from ..optionsdata import BUILTIN_PROFILES
from .common import EmptyState, IconField

PROFILE_ROLE = Qt.ItemDataRole.UserRole + 1
ID_ROLE = Qt.ItemDataRole.UserRole + 2


class ProfilePanel(QWidget):
    """Built-in and user-saved scan profiles."""

    profile_chosen = pyqtSignal(dict)
    save_requested = pyqtSignal()

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.user_profiles: list[dict] = storage.load_user_profiles()

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        root.setSpacing(SPACE["md"])

        self.search = IconField("search", pal, self)
        self.search.setPlaceholderText("Search profiles…")
        self.search.textChanged.connect(self.reload)
        root.addWidget(self.search)

        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        self.list.itemSelectionChanged.connect(self._show_detail)
        self.list.itemDoubleClicked.connect(self._apply_current)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        root.addWidget(self.list, 1)

        self.detail = QTextBrowser(self)
        self.detail.setMaximumHeight(124)
        root.addWidget(self.detail)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE["sm"])
        apply_btn = QPushButton("Apply", self)
        apply_btn.setProperty("accent", "true")
        apply_btn.setMinimumHeight(HIT["comfortable"])
        apply_btn.clicked.connect(self._apply_current)
        buttons.addWidget(apply_btn)

        save_btn = QPushButton("Save current…", self)
        save_btn.setMinimumHeight(HIT["comfortable"])
        save_btn.setIcon(icons.icon("save", pal["dim"], 15))
        save_btn.clicked.connect(self.save_requested.emit)
        buttons.addWidget(save_btn)
        root.addLayout(buttons)

        self.reload()

    def restyle(self) -> None:
        self.reload()
        self._show_detail()

    # ------------------------------------------------------------------ data
    def reload(self) -> None:
        needle = self.search.text().strip().lower()
        self.list.clear()
        for profile in BUILTIN_PROFILES:
            data = {"name": profile.name, "description": profile.description,
                    "opts": dict(profile.opts), "scripts": list(profile.scripts),
                    "script_args": profile.script_args, "builtin": True}
            self._maybe_add(data, needle, builtin=True)
        for data in self.user_profiles:
            self._maybe_add(dict(data, builtin=False), needle, builtin=False)

    def _maybe_add(self, data: dict, needle: str, builtin: bool) -> None:
        hay = f"{data['name']} {data.get('description', '')}".lower()
        if needle and needle not in hay:
            return
        item = QListWidgetItem(data["name"])
        item.setData(PROFILE_ROLE, data)
        item.setIcon(icons.icon("star" if builtin else "star-outline",
                                self.pal["accent"] if builtin else self.pal["purple"], 15))
        item.setToolTip(data.get("description", ""))
        self.list.addItem(item)

    def add_user_profile(self, data: dict) -> None:
        self.user_profiles = [p for p in self.user_profiles if p["name"] != data["name"]]
        self.user_profiles.append(data)
        storage.save_user_profiles(self.user_profiles)
        self.reload()

    # ----------------------------------------------------------------- ui
    def _current(self) -> dict | None:
        item = self.list.currentItem()
        return item.data(PROFILE_ROLE) if item else None

    def _apply_current(self, *_args) -> None:
        data = self._current()
        if data:
            self.profile_chosen.emit(data)

    def _show_detail(self) -> None:
        data = self._current()
        pal = self.pal
        if not data:
            self.detail.clear()
            return
        from ..command import ScanConfig
        preview = ScanConfig(targets="TARGET", opts=data.get("opts", {}),
                             scripts=data.get("scripts", []),
                             script_args=data.get("script_args", "")).preview()
        preview = html.escape(preview)
        name = html.escape(data["name"])
        description = html.escape(data.get("description", ""))
        self.detail.setHtml(
            f'<div style="font-family:sans-serif;color:{pal["dim"]};padding:6px 8px;'
            f'font-size:{TYPE["body"]}px;">'
            f'<b style="color:{pal["text"]};">{name}</b><br>'
            f'{description}'
            f'<pre style="color:{pal["accent"]};white-space:pre-wrap;margin-top:8px;">'
            f'{preview}</pre></div>')

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        data = item.data(PROFILE_ROLE)
        menu = QMenu(self)
        menu.addAction("Apply", self._apply_current)
        if not data.get("builtin"):
            menu.addAction("Rename…", lambda: self._rename(data))
            menu.addAction("Delete", lambda: self._delete(data))
        else:
            menu.addAction("Duplicate as editable copy", lambda: self._duplicate(data))
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _rename(self, data: dict) -> None:
        name, ok = QInputDialog.getText(self, "Rename profile", "New name:", text=data["name"])
        if ok and name.strip():
            for profile in self.user_profiles:
                if profile["name"] == data["name"]:
                    profile["name"] = name.strip()
            storage.save_user_profiles(self.user_profiles)
            self.reload()

    def _delete(self, data: dict) -> None:
        confirm = QMessageBox.question(self, "Delete profile",
                                       f"Delete the profile “{data['name']}”?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.user_profiles = [p for p in self.user_profiles if p["name"] != data["name"]]
            storage.save_user_profiles(self.user_profiles)
            self.reload()

    def _duplicate(self, data: dict) -> None:
        copy = dict(data)
        copy["name"] = f"{data['name']} (copy)"
        copy["builtin"] = False
        self.add_user_profile(copy)


class HistoryPanel(QWidget):
    """Every scan that has been run, stored in SQLite."""

    open_requested = pyqtSignal(int)
    compare_requested = pyqtSignal(int, int)

    def __init__(self, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        root.setSpacing(SPACE["md"])

        self.search = IconField("search", pal, self)
        self.search.setPlaceholderText("Search history — target, command, title…")
        self.search.textChanged.connect(self.reload)
        root.addWidget(self.search)

        self.stack = QStackedWidget(self)
        self.empty = EmptyState(
            "history", "No scans yet",
            "Every scan you run is saved here automatically — reopen one in a new "
            "tab, or select two and compare what changed between them.", pal, self)
        self.stack.addWidget(self.empty)

        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemDoubleClicked.connect(self._open_current)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.stack.addWidget(self.list)
        root.addWidget(self.stack, 1)

        info = QHBoxLayout()
        self.count = QLabel("", self)
        self.count.setProperty("role", "dim")
        info.addWidget(self.count, 1)
        self.compare_btn = QPushButton("Compare two", self)
        self.compare_btn.setMinimumHeight(HIT["comfortable"])
        self.compare_btn.setIcon(icons.icon("compare", pal["dim"], 15))
        self.compare_btn.setToolTip("Select exactly two scans, then diff them")
        self.compare_btn.clicked.connect(self._compare_selected)
        info.addWidget(self.compare_btn)
        root.addLayout(info)

        self.reload()

    def restyle(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        entries = storage.list_scans(self.search.text().strip())
        for entry in entries:
            item = QListWidgetItem(
                f"{entry.title}\n{entry.when} · {entry.hosts_up} up · "
                f"{entry.open_ports} open · {entry.duration:.0f}s")
            item.setData(ID_ROLE, entry.id)
            item.setIcon(icons.icon(
                "check" if entry.status == "finished" else "warning",
                self.pal["open"] if entry.status == "finished" else self.pal["filtered"], 15))
            item.setToolTip(entry.command)
            self.list.addItem(item)

        searching = bool(self.search.text().strip())
        self.stack.setCurrentIndex(1 if (entries or searching) else 0)
        self.compare_btn.setEnabled(len(entries) > 1)
        if searching and not entries:
            self.count.setText("nothing matches that search")
        else:
            self.count.setText(
                f"{len(entries)} scan{'' if len(entries) == 1 else 's'} stored")

    def _open_current(self, *_args) -> None:
        item = self.list.currentItem()
        if item:
            self.open_requested.emit(item.data(ID_ROLE))

    def _compare_selected(self) -> None:
        items = self.list.selectedItems()
        if len(items) != 2:
            QMessageBox.information(self, "Compare scans",
                                    "Select exactly two scans to compare.")
            return
        self.compare_requested.emit(items[0].data(ID_ROLE), items[1].data(ID_ROLE))

    def _menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        scan_id = item.data(ID_ROLE)
        menu = QMenu(self)
        menu.addAction(icons.icon("folder", self.pal["dim"], 15), "Open in a new tab",
                       self._open_current)
        menu.addAction("Rename…", lambda: self._rename(scan_id))
        menu.addSeparator()
        menu.addAction("Compare selected two", self._compare_selected)
        menu.addSeparator()
        menu.addAction(icons.icon("trash", self.pal["closed"], 15), "Delete",
                       lambda: self._delete(scan_id))
        menu.addAction("Clear all history…", self._clear)
        menu.exec(self.list.viewport().mapToGlobal(pos))

    def _rename(self, scan_id: int) -> None:
        name, ok = QInputDialog.getText(self, "Rename scan", "Title:")
        if ok and name.strip():
            storage.rename_scan(scan_id, name.strip())
            self.reload()

    def _delete(self, scan_id: int) -> None:
        storage.delete_scan(scan_id)
        self.reload()

    def _clear(self) -> None:
        confirm = QMessageBox.question(
            self, "Clear history", "Delete every stored scan? This cannot be undone.")
        if confirm == QMessageBox.StandardButton.Yes:
            storage.clear_history()
            self.reload()
