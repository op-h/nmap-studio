"""Browse, search and select NSE scripts."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                             QSplitter, QTextBrowser, QVBoxLayout, QWidget)

from .. import icons
from ..design import HIT, SPACE, TYPE
from ..nse import Script, all_categories, load_catalogue
from ..optionsdata import CATEGORY_RISK, NSE_CATEGORIES
from .common import IconField

RISK_LABEL = {"low": "safe", "medium": "care", "high": "risky"}


class ScriptBrowser(QWidget):
    """Left: filterable script list with checkboxes. Right: script documentation."""

    changed = pyqtSignal()

    def __init__(self, palette: dict, parent=None):
        super().__init__(parent)
        self.pal = palette
        self.catalogue: list[Script] = []
        self.by_name: dict[str, Script] = {}
        self.selected: set[str] = set()
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        root.setSpacing(SPACE["md"])

        # ---- filters
        filters = QHBoxLayout()
        filters.setSpacing(SPACE["md"])
        self.search = IconField("search", palette, self)
        self.search.setPlaceholderText("Search scripts…")
        self.search.textChanged.connect(self._refill)
        filters.addWidget(self.search, 1)

        self.category = QComboBox(self)
        self.category.setMinimumWidth(170)
        self.category.setMinimumHeight(HIT["min"])
        self.category.currentIndexChanged.connect(self._refill)
        filters.addWidget(self.category, 0)
        root.addLayout(filters)

        self.only_selected = QCheckBox("Selected only", self)
        self.only_selected.toggled.connect(self._refill)
        self.deep_search = QCheckBox("Search descriptions", self)
        self.deep_search.setToolTip(
            "Off: match script names only. On: also search the description text — "
            "broader, but most descriptions mention a URL so 'http' matches nearly "
            "everything.")
        self.deep_search.toggled.connect(self._refill)
        hide_row = QHBoxLayout()
        hide_row.addWidget(self.only_selected)
        hide_row.addWidget(self.deep_search)
        hide_row.addStretch(1)
        self.count_label = QLabel("", self)
        self.count_label.setProperty("role", "dim")
        hide_row.addWidget(self.count_label)
        root.addLayout(hide_row)

        # ---- list + detail
        split = QSplitter(Qt.Orientation.Vertical, self)
        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentItemChanged.connect(self._show_detail)
        split.addWidget(self.list)

        self.detail = QTextBrowser(self)
        self.detail.setOpenExternalLinks(True)
        self.detail.setMinimumHeight(120)
        split.addWidget(self.detail)
        split.setSizes([460, 220])
        root.addWidget(split, 1)

        # ---- selection summary and args
        self.chosen = QLineEdit(self)
        self.chosen.setProperty("mono", "true")
        self.chosen.setPlaceholderText("--script  (click scripts above, or type names/categories)")
        self.chosen.textChanged.connect(self._on_chosen_edited)
        root.addWidget(self.chosen)

        self.script_args = QLineEdit(self)
        self.script_args.setProperty("mono", "true")
        self.script_args.setPlaceholderText(
            "--script-args   e.g. http-title.url=/admin,userdb=/tmp/users.txt")
        self.script_args.textChanged.connect(lambda *_: self.changed.emit())
        root.addWidget(self.script_args)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE["sm"])
        for label, handler, tip in (
                ("default", lambda: self._add_category("default"),
                 "Everything -sC would run"),
                ("safe", lambda: self._add_category("safe"), "Non-intrusive scripts only"),
                ("vuln", lambda: self._add_category("vuln"), "Known-vulnerability checks"),
                ("discovery", lambda: self._add_category("discovery"), "Pull more detail out")):
            btn = QPushButton(label, self)
            btn.setProperty("flat", "true")
            btn.setMinimumHeight(HIT["min"])
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            buttons.addWidget(btn)
        buttons.addStretch(1)
        clear = QPushButton("Clear", self)
        clear.setProperty("flat", "true")
        clear.setMinimumHeight(HIT["min"])
        clear.clicked.connect(self.clear)
        buttons.addWidget(clear)
        root.addLayout(buttons)

        self.reload()

    def restyle(self) -> None:
        self._refill()
        self._show_detail(self.list.currentItem())

    # --------------------------------------------------------------- loading
    def reload(self) -> None:
        self.catalogue = load_catalogue()
        self.by_name = {s.name: s for s in self.catalogue}
        known = {c for c, _ in NSE_CATEGORIES} | set(all_categories(self.catalogue))
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("All categories", "")
        for cat in sorted(known):
            blurb = dict(NSE_CATEGORIES).get(cat, "")
            self.category.addItem(f"{cat}" + (f" — {blurb[:40]}" if blurb else ""), cat)
        self.category.blockSignals(False)
        self._refill()

    def _refill(self) -> None:
        needle = self.search.text().strip().lower()
        cat = self.category.currentData() or ""
        self._loading = True
        self.list.clear()
        shown = 0

        # Name matches first: a description search for "http" would otherwise bury
        # http-title under every script whose docs happen to link to a URL.
        matches: list[tuple[int, Script]] = []
        for script in self.catalogue:
            if cat and cat not in script.categories:
                continue
            if self.only_selected.isChecked() and script.name not in self.selected:
                continue
            if not needle:
                matches.append((0, script))
                continue
            if needle in script.name.lower():
                matches.append((0, script))
            elif self.deep_search.isChecked() and needle in script.description.lower():
                matches.append((1, script))
        matches.sort(key=lambda pair: (pair[0], pair[1].name))

        for rank, script in matches:
            item = QListWidgetItem(script.name)
            item.setData(Qt.ItemDataRole.UserRole, script.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if script.name in self.selected
                               else Qt.CheckState.Unchecked)
            risk = max((CATEGORY_RISK.get(c, "low") for c in script.categories),
                       key=lambda r: {"low": 0, "medium": 1, "high": 2}[r], default="low")
            colour = {"low": self.pal["open"], "medium": self.pal["filtered"],
                      "high": self.pal["closed"]}[risk]
            item.setIcon(icons.icon("script", colour, 16))
            item.setToolTip(f"{', '.join(script.categories)}\n\n{script.summary}")
            if rank:
                item.setForeground(QBrush(QColor(self.pal["dim"])))
            self.list.addItem(item)
            shown += 1
        self._loading = False
        self.count_label.setText(f"{shown} shown · {len(self.selected)} selected · "
                                 f"{len(self.catalogue)} installed")

    # ------------------------------------------------------------- selection
    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.selected.add(name)
        else:
            self.selected.discard(name)
        self._sync_chosen()

    def _on_chosen_edited(self, text: str) -> None:
        if self._loading:
            return
        self.selected = {part.strip() for part in text.split(",") if part.strip()}
        self._loading = True
        for i in range(self.list.count()):
            item = self.list.item(i)
            name = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Checked if name in self.selected
                               else Qt.CheckState.Unchecked)
        self._loading = False
        self.count_label.setText(f"{self.list.count()} shown · {len(self.selected)} selected · "
                                 f"{len(self.catalogue)} installed")
        self.changed.emit()

    def _sync_chosen(self) -> None:
        self._loading = True
        self.chosen.setText(",".join(sorted(self.selected)))
        self._loading = False
        self.count_label.setText(f"{self.list.count()} shown · {len(self.selected)} selected · "
                                 f"{len(self.catalogue)} installed")
        self.changed.emit()

    def _add_category(self, category: str) -> None:
        self.selected.add(category)
        self._sync_chosen()
        self._refill()

    def clear(self) -> None:
        self.selected.clear()
        self.script_args.clear()
        self._sync_chosen()
        self._refill()

    # ---------------------------------------------------------------- detail
    def _show_detail(self, item: QListWidgetItem | None, _prev=None) -> None:
        if item is None:
            self.detail.clear()
            return
        script = self.by_name.get(item.data(Qt.ItemDataRole.UserRole))
        if script is None:
            self.detail.clear()
            return
        pal = self.pal
        cats = " · ".join(script.categories) or "uncategorised"
        args = "".join(
            f'<tr><td style="padding:2px 10px 2px 0;color:{pal["cyan"]};white-space:nowrap;">'
            f'<code>{name}</code></td><td style="color:{pal["dim"]};">{desc}</td></tr>'
            for name, desc in script.args)
        html = [
            f'<div style="font-family:sans-serif;color:{pal["text"]};">',
            f'<h3 style="margin:0 0 4px;color:{pal["text"]};">{script.name}</h3>',
            f'<div style="margin-bottom:8px;color:{pal["accent"]};">{cats}</div>',
            f'<div style="color:{pal["dim"]};white-space:pre-wrap;">'
            f'{script.description or "No description in the script source."}</div>',
        ]
        if args:
            html.append(f'<h4 style="margin:12px 0 4px;color:{pal["text"]};">Arguments</h4>'
                        f'<table>{args}</table>')
        if script.usage:
            html.append(f'<h4 style="margin:12px 0 4px;color:{pal["text"]};">Usage</h4>'
                        f'<pre style="color:{pal["open"]};white-space:pre-wrap;">'
                        f'{script.usage}</pre>')
        if script.author:
            html.append(f'<div style="margin-top:12px;color:{pal["faint"]};'
                        f'font-size:{TYPE["small"]}px;">'
                        f'author: {script.author} · license: {script.license}</div>')
        html.append("</div>")
        self.detail.setHtml("".join(html))

    # ------------------------------------------------------------------ api
    def scripts(self) -> list[str]:
        return sorted(self.selected)

    def args_text(self) -> str:
        return self.script_args.text().strip()

    def set_state(self, scripts: list[str], args: str = "") -> None:
        self.selected = set(scripts)
        self.script_args.setText(args)
        self._sync_chosen()
        self._refill()

    def risky_selection(self) -> list[str]:
        """Selected entries in a category that can disrupt the target."""
        risky = []
        for name in sorted(self.selected):
            cats = self.by_name[name].categories if name in self.by_name else (name,)
            if any(CATEGORY_RISK.get(c) == "high" for c in cats):
                risky.append(name)
        return risky
