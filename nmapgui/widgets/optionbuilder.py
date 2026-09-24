"""The full nmap option surface, generated from the catalogue."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea,
                             QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from .. import icons
from ..design import HIT, RADIUS, SPACE, TYPE
from ..optionsdata import CHOICE, EXCLUSIVE, FILE, FLAG, INT, OPTIONS, SECTIONS, TEXT
from .collapsible import Section
from .common import IconField


class OptionRow(QWidget):
    """One catalogue entry: a toggle, an optional value editor and its help text."""

    changed = pyqtSignal()
    hovered = pyqtSignal(object)

    def __init__(self, opt, palette: dict, parent=None):
        super().__init__(parent)
        self.opt = opt
        self.pal = palette
        self.value_widget = None

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE["sm"], 2, SPACE["sm"], 2)
        root.setSpacing(2)

        line = QHBoxLayout()
        line.setSpacing(SPACE["md"])

        if opt.kind == EXCLUSIVE:
            self.toggle = QRadioButton(opt.label, self)
            self.toggle.setAutoExclusive(False)
        else:
            self.toggle = QCheckBox(opt.label, self)
        self.toggle.setToolTip(f"{opt.flag}\n\n{opt.help}" if opt.help else opt.flag)
        self.toggle.toggled.connect(self._on_toggle)
        # Let a long label give up width first, so the flag chip and the
        # root shield never get pushed out of a narrow dock.
        self.toggle.setSizePolicy(QSizePolicy.Policy.Ignored,
                                  QSizePolicy.Policy.Preferred)
        self.toggle.setMinimumWidth(90)
        line.addWidget(self.toggle, 1)

        self.flag_chip = QLabel(opt.flag, self)
        self.flag_chip.setProperty("role", "mono")
        line.addWidget(self.flag_chip, 0, Qt.AlignmentFlag.AlignRight)

        self.shield = QLabel(self)
        self.shield.setFixedWidth(15)
        if opt.root:
            self.shield.setPixmap(icons.icon("shield", palette["filtered"], 13).pixmap(13, 13))
            self.shield.setToolTip("Needs root / administrator")
        line.addWidget(self.shield, 0)
        root.addLayout(line)

        # The value editor only appears once the option is switched on.
        if opt.kind in (TEXT, INT, CHOICE, FILE):
            self.value_row = QWidget(self)
            value_line = QHBoxLayout(self.value_row)
            value_line.setContentsMargins(22, 0, 15, 2)
            value_line.setSpacing(SPACE["sm"])
            self.value_widget = self._make_value_widget(opt)
            value_line.addWidget(self.value_widget, 1)
            if opt.kind == FILE:
                browse = QPushButton("Browse…", self.value_row)
                browse.setProperty("flat", "true")
                browse.setMinimumHeight(HIT["min"] - 4)
                browse.clicked.connect(self._browse)
                value_line.addWidget(browse, 0)
            root.addWidget(self.value_row)
            self.value_row.setVisible(False)

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.restyle()

    def restyle(self) -> None:
        pal = self.pal
        self.setStyleSheet(
            f"OptionRow {{ border-radius: {RADIUS['control']}px; }}"
            f"OptionRow:hover {{ background: {pal['surface2']}; }}")
        self._style_chip(self.toggle.isChecked())

    def enterEvent(self, event):
        self.hovered.emit(self.opt)
        super().enterEvent(event)

    # ---------------------------------------------------------------- widgets
    def _make_value_widget(self, opt) -> QWidget:
        if opt.kind == CHOICE:
            box = QComboBox(self)
            for choice in opt.choices:
                box.addItem(choice or "(default)", choice)
            box.currentIndexChanged.connect(lambda *_: self.changed.emit())
            return box
        if opt.kind == INT:
            spin = QSpinBox(self)
            spin.setRange(opt.lo, opt.hi)
            spin.setSpecialValueText(" ")
            if opt.placeholder.isdigit():
                spin.setValue(min(max(int(opt.placeholder), opt.lo), opt.hi))
            spin.valueChanged.connect(lambda *_: self.changed.emit())
            return spin
        edit = QLineEdit(self)
        edit.setPlaceholderText(opt.placeholder or "value")
        edit.setProperty("mono", "true")
        edit.textChanged.connect(lambda *_: self.changed.emit())
        return edit

    def _browse(self) -> None:
        if self.opt.key == "datadir":
            path = QFileDialog.getExistingDirectory(self, f"Choose directory for {self.opt.flag}")
        elif self.opt.key in ("oN", "oG", "oS"):
            path, _ = QFileDialog.getSaveFileName(self, f"Output file for {self.opt.flag}")
        else:
            path, _ = QFileDialog.getOpenFileName(self, f"Choose file for {self.opt.flag}")
        if path:
            self.value_widget.setText(path)
            self.toggle.setChecked(True)

    def _style_chip(self, active: bool) -> None:
        pal = self.pal
        colour = pal["accent"] if active else pal["dim"]
        background = pal["accent_dim"] if active else pal["surface2"]
        self.flag_chip.setStyleSheet(
            f"color:{colour};background:{background};"
            f"border-radius:{RADIUS['chip']}px;padding:1px 6px;")

    def _on_toggle(self, checked: bool) -> None:
        self._style_chip(checked)
        if self.value_widget is not None:
            self.value_row.setVisible(checked)
            self.value_widget.setEnabled(checked)
            if checked and self.isVisible():
                self.value_widget.setFocus()
        self.changed.emit()

    # ------------------------------------------------------------------ value
    def is_on(self) -> bool:
        return self.toggle.isChecked()

    def value(self):
        if not self.toggle.isChecked():
            return None
        if self.value_widget is None:
            return True
        if isinstance(self.value_widget, QComboBox):
            return self.value_widget.currentData()
        if isinstance(self.value_widget, QSpinBox):
            val = self.value_widget.value()
            return "" if val == self.value_widget.minimum() and self.opt.lo == 0 else str(val)
        return self.value_widget.text().strip()

    def set_value(self, value) -> None:
        block = self.blockSignals(True)
        try:
            if value in (None, False):
                self.toggle.setChecked(False)
                self._style_chip(False)
                if self.value_widget is not None:
                    self.value_row.setVisible(False)
                return
            self.toggle.setChecked(True)
            self._style_chip(True)
            if self.value_widget is not None:
                self.value_row.setVisible(True)
            if self.value_widget is None:
                return
            text = "" if value is True else str(value)
            if isinstance(self.value_widget, QComboBox):
                index = self.value_widget.findData(text)
                self.value_widget.setCurrentIndex(max(index, 0))
            elif isinstance(self.value_widget, QSpinBox):
                self.value_widget.setValue(int(text) if text.lstrip("-").isdigit()
                                           else self.value_widget.minimum())
            else:
                self.value_widget.setText(text)
            self.value_widget.setEnabled(True)
        finally:
            self.blockSignals(block)

    def matches(self, needle: str) -> bool:
        needle = needle.lower()
        return (needle in self.opt.label.lower() or needle in self.opt.flag.lower()
                or needle in self.opt.help.lower() or needle in self.opt.key.lower())


class OptionBuilder(QWidget):
    """Search box + collapsible sections covering every catalogued nmap flag."""

    changed = pyqtSignal()

    IDLE_HELP = "Point at an option to see what it does."

    def __init__(self, palette: dict, parent=None):
        super().__init__(parent)
        self.pal = palette
        self.rows: dict[str, OptionRow] = {}
        self.sections: dict[str, Section] = {}
        self._exclusive: dict[str, QButtonGroup] = {}
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], 0)
        self.search = IconField("search", palette, self)
        self.search.setPlaceholderText("Filter options — try udp, decoy, rate, script")
        self.search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search)

        clear = QPushButton(self)
        clear.setIcon(icons.icon("refresh", palette["dim"], 15))
        clear.setToolTip("Reset every option")
        clear.setProperty("flat", "true")
        clear.setFixedSize(HIT["comfortable"], HIT["comfortable"])
        clear.clicked.connect(self.reset)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.inner_layout = QVBoxLayout(inner)
        self.inner_layout.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["xl"])
        self.inner_layout.setSpacing(SPACE["md"])

        default_open = {"technique", "ports"}
        for key, title, blurb in SECTIONS:
            # The subtitle is dropped: the section title plus the help strip
            # at the foot of the panel already explain it.
            section = Section(title, "", expanded=key in default_open, pal=palette)
            self.sections[key] = section
            self.inner_layout.addWidget(section)

        for opt in OPTIONS:
            row = OptionRow(opt, palette, self)
            row.changed.connect(self._on_row_changed)
            row.hovered.connect(self._show_help)
            self.rows[opt.key] = row
            self.sections[opt.section].add(row)
            if opt.kind == EXCLUSIVE:
                group = self._exclusive.setdefault(opt.exclusive, QButtonGroup(self))
                group.setExclusive(False)
                group.addButton(row.toggle)

        self.inner_layout.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # One explanation at a time, for whatever the pointer is on — instead of
        # a sentence under all 100 rows.
        self.help_strip = QLabel(self)
        self.help_strip.setWordWrap(True)
        self.help_strip.setMinimumHeight(52)
        self.help_strip.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.help_strip.setContentsMargins(SPACE["lg"], SPACE["md"],
                                           SPACE["lg"], SPACE["md"])
        self.help_strip.setText(self.IDLE_HELP)
        self._style_help_strip()
        root.addWidget(self.help_strip, 0)

    # ------------------------------------------------------------- behaviour
    def _style_help_strip(self) -> None:
        pal = self.pal
        self.help_strip.setStyleSheet(
            f"QLabel {{ color:{pal['dim']}; background:{pal['surface']};"
            f"border-top:1px solid {pal['line']}; font-size:{TYPE['small']}px; }}")

    def _show_help(self, opt) -> None:
        pal = self.pal
        self.help_strip.setText(
            f'<span style="color:{pal["accent"]};font-family:monospace;">{opt.flag}</span>'
            f'&nbsp;&nbsp;<span style="color:{pal["text"]};">{opt.label}</span><br>'
            f'{opt.help}')

    def leaveEvent(self, event):
        self.help_strip.setText(self.IDLE_HELP)
        super().leaveEvent(event)

    def restyle(self) -> None:
        self._style_help_strip()

    def _on_row_changed(self) -> None:
        if self._loading:
            return
        sender = self.sender()
        if isinstance(sender, OptionRow) and sender.opt.kind == EXCLUSIVE and sender.is_on():
            self._loading = True
            try:
                for row in self.rows.values():
                    if (row is not sender and row.opt.kind == EXCLUSIVE
                            and row.opt.exclusive == sender.opt.exclusive and row.is_on()):
                        row.toggle.setChecked(False)
            finally:
                self._loading = False
        self._update_badges()
        self.changed.emit()

    def _update_badges(self) -> None:
        counts: dict[str, int] = {}
        for row in self.rows.values():
            if row.is_on():
                counts[row.opt.section] = counts.get(row.opt.section, 0) + 1
        for key, section in self.sections.items():
            section.set_badge(counts.get(key, 0))

    def _apply_filter(self, text: str) -> None:
        text = text.strip()
        for key, section in self.sections.items():
            visible_rows = 0
            for row in self.rows.values():
                if row.opt.section != key:
                    continue
                show = not text or row.matches(text)
                row.setVisible(show)
                visible_rows += int(show)
            section.setVisible(visible_rows > 0)
            if text and visible_rows:
                section.set_expanded(True, animate=False)

    # ----------------------------------------------------------------- state
    def options(self) -> dict:
        out = {}
        for key, row in self.rows.items():
            value = row.value()
            if value is None:
                continue
            out[key] = value
            if value == "" and row.opt.kind != FLAG:
                out[f"{key}__on"] = True
        return out

    def set_options(self, opts: dict) -> None:
        self._loading = True
        try:
            for key, row in self.rows.items():
                row.set_value(opts.get(key))
        finally:
            self._loading = False
        self._update_badges()
        self.changed.emit()

    def reset(self) -> None:
        self.set_options({})

    def expand_all(self, expanded: bool = True) -> None:
        for section in self.sections.values():
            section.set_expanded(expanded)

    def highlight(self, keys) -> None:
        """Open the sections that contain the given option keys."""
        wanted = {self.rows[k].opt.section for k in keys if k in self.rows}
        for key, section in self.sections.items():
            if key in wanted:
                section.set_expanded(True)
