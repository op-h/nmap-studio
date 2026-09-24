"""Live nmap output with syntax colouring and an incremental find bar."""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                         QTextDocument)
from PyQt6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                             QPushButton, QVBoxLayout, QWidget)

from .. import icons
from ..design import HIT, RADIUS, SPACE
from ..theme import mono_family
from .common import IconField


class NmapHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, pal: dict):
        super().__init__(document)
        self.rules = []

        def fmt(colour: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(colour))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        self.rules = [
            (re.compile(r"^\$ .*$"), fmt(pal["accent"], bold=True)),
            (re.compile(r"^\[nmap-studio\].*$"), fmt(pal["cyan"], italic=True)),
            (re.compile(r"^Nmap scan report for .*$"), fmt(pal["accent"], bold=True)),
            (re.compile(r"^(Starting Nmap|Nmap done:).*$"), fmt(pal["purple"])),
            (re.compile(r"\b(\d{1,5}/(?:tcp|udp|sctp))\b"), fmt(pal["cyan"])),
            (re.compile(r"\bopen\b(?!\|)"), fmt(pal["open"], bold=True)),
            (re.compile(r"\bclosed\b"), fmt(pal["closed"])),
            (re.compile(r"\b(filtered|open\|filtered|closed\|filtered)\b"), fmt(pal["filtered"])),
            (re.compile(r"^Discovered open port .*$"), fmt(pal["open"])),
            (re.compile(r"^\|.*$"), fmt(pal["purple"])),
            (re.compile(r"^(Stats:|.*Timing: About).*$"), fmt(pal["faint"], italic=True)),
            (re.compile(r"(?i)^(warning|error|failed|QUITTING).*$"), fmt(pal["closed"], bold=True)),
            (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), fmt(pal["accent"])),
            (re.compile(r"\bHost is up\b.*$"), fmt(pal["open"])),
            (re.compile(r"\|_?\s*VULNERABLE.*$"), fmt(pal["closed"], bold=True)),
        ]

    def highlightBlock(self, text: str) -> None:
        for pattern, form in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), form)


class OutputView(QWidget):
    """Terminal-style pane: appends fast, colourises, and can be searched."""

    def __init__(self, pal: dict, mono_size: int = 10, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._pending = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, SPACE["md"], 0, 0)
        bar.setSpacing(SPACE["md"])
        self.find = IconField("search", pal, self)
        self.find.setPlaceholderText("Find in output — Enter for next, Shift+Enter for previous")
        self.find.returnPressed.connect(self.find_next)
        self.find.textChanged.connect(self._reset_search)
        bar.addWidget(self.find, 1)

        prev_btn = QPushButton(self)
        prev_btn.setIcon(icons.icon("arrow-up", pal["dim"], 15))
        prev_btn.setProperty("flat", "true")
        prev_btn.setFixedSize(HIT["min"], HIT["min"])
        prev_btn.setToolTip("Previous match  (Shift+Enter)")
        prev_btn.clicked.connect(self.find_prev)
        bar.addWidget(prev_btn)

        next_btn = QPushButton(self)
        next_btn.setIcon(icons.icon("arrow-down", pal["dim"], 15))
        next_btn.setProperty("flat", "true")
        next_btn.setFixedSize(HIT["min"], HIT["min"])
        next_btn.setToolTip("Next match  (Enter)")
        next_btn.clicked.connect(self.find_next)
        bar.addWidget(next_btn)

        self.hits = QLabel("", self)
        self.hits.setProperty("role", "dim")
        bar.addWidget(self.hits)

        self.autoscroll = QCheckBox("Follow", self)
        self.autoscroll.setChecked(True)
        self.autoscroll.setToolTip("Keep scrolling to the newest output")
        bar.addWidget(self.autoscroll)

        self.wrap = QCheckBox("Wrap", self)
        self.wrap.toggled.connect(self._set_wrap)
        bar.addWidget(self.wrap)
        root.addLayout(bar)

        self.text = QPlainTextEdit(self)
        self.text.setReadOnly(True)
        self.text.setUndoRedoEnabled(False)
        self.text.setMaximumBlockCount(200_000)
        self.text.setPlaceholderText(
            "  nmap's console output streams here, line by line, as the scan runs.")
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont(mono_family())
        font.setPointSize(mono_size)
        self.text.setFont(font)
        root.addWidget(self.text, 1)

        self.highlighter = NmapHighlighter(self.text.document(), pal)
        self.restyle()

    def restyle(self) -> None:
        pal = self.pal
        self.text.setStyleSheet(
            f"QPlainTextEdit{{background:{pal['term_bg']};border:1px solid {pal['line']};"
            f"border-radius:{RADIUS['panel']}px;padding:{SPACE['lg']}px;"
            f"color:{pal['text']};}}")
        # The highlighter caches its colours, so it is rebuilt rather than reused.
        self.highlighter = NmapHighlighter(self.text.document(), pal)
        self.highlighter.rehighlight()

    # ------------------------------------------------------------------ text
    def append(self, chunk: str) -> None:
        bar = self.text.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        if self.autoscroll.isChecked() or at_end:
            bar.setValue(bar.maximum())

    def set_text(self, text: str) -> None:
        self.text.setPlainText(text)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

    def clear(self) -> None:
        self.text.clear()

    def plain_text(self) -> str:
        return self.text.toPlainText()

    def _set_wrap(self, on: bool) -> None:
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if on
                                  else QPlainTextEdit.LineWrapMode.NoWrap)

    # ---------------------------------------------------------------- search
    def _reset_search(self) -> None:
        needle = self.find.text()
        if not needle:
            self.hits.setText("")
            return
        count = self.plain_text().lower().count(needle.lower())
        self.hits.setText(f"{count} match{'' if count == 1 else 'es'}")

    def find_next(self) -> None:
        self._search(QTextDocument.FindFlag(0))

    def find_prev(self) -> None:
        self._search(QTextDocument.FindFlag.FindBackward)

    def _search(self, flags) -> None:
        needle = self.find.text()
        if not needle:
            return
        if not self.text.find(needle, flags):
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End
                                if flags & QTextDocument.FindFlag.FindBackward
                                else QTextCursor.MoveOperation.Start)
            self.text.setTextCursor(cursor)
            self.text.find(needle, flags)
