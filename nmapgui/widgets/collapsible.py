"""An animated collapsible section, used by the option builder."""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)

from .. import icons
from ..design import DURATION, RADIUS, SPACE, TYPE


class SectionHeader(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)          # a comfortable hit area
        self._open = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["md"])

        self.chevron = QLabel(self)
        self.chevron.setFixedWidth(14)
        layout.addWidget(self.chevron)

        self.title = QLabel(title, self)
        layout.addWidget(self.title, 1)

        self.badge = QLabel("", self)
        self.badge.setVisible(False)
        layout.addWidget(self.badge)
        self.restyle()

    def restyle(self) -> None:
        pal = self.pal
        self.setStyleSheet(
            f"SectionHeader {{ border-radius: {RADIUS['panel']}px; }}"
            f"SectionHeader:hover {{ background: {pal['surface2']}; }}")
        self.title.setStyleSheet(
            f"color:{pal['text']};font-size:{TYPE['medium']}px;font-weight:600;")
        self.badge.setStyleSheet(
            f"color:{pal['accent']};background:{pal['accent_dim']};"
            f"border-radius:{RADIUS['chip']}px;padding:1px 7px;"
            f"font-size:{TYPE['micro']}px;font-weight:700;")
        self.set_open(self._open)

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.chevron.setPixmap(icons.icon(
            "chevron-down" if is_open else "chevron-right",
            self.pal["dim"], 14).pixmap(14, 14))

    def set_badge(self, count: int) -> None:
        self.badge.setVisible(count > 0)
        self.badge.setText(str(count))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Section(QFrame):
    """A card whose body slides open and shut."""

    toggled_open = pyqtSignal(bool)

    def __init__(self, title: str, subtitle: str = "", expanded: bool = False,
                 pal: dict | None = None, parent=None):
        super().__init__(parent)
        self.pal = pal or {}
        self.setProperty("role", "card")
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = SectionHeader(title, self.pal, self)
        self.header.clicked.connect(self.toggle)
        outer.addWidget(self.header)

        self.body = QWidget(self)
        self.body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(SPACE["lg"], 0, SPACE["lg"], SPACE["lg"])
        self.body_layout.setSpacing(SPACE["xs"])

        self.note = None
        if subtitle:
            self.note = QLabel(subtitle, self.body)
            self.note.setWordWrap(True)
            self.note.setContentsMargins(0, 0, 0, SPACE["sm"])
            self.body_layout.addWidget(self.note)
            self._style_note()

        outer.addWidget(self.body)

        self._anim = QPropertyAnimation(self.body, b"maximumHeight", self)
        self._anim.finished.connect(self._on_anim_done)
        self.header.set_open(expanded)
        self.body.setMaximumHeight(16777215 if expanded else 0)
        self.body.setVisible(expanded)

    # ------------------------------------------------------------------ api
    def _style_note(self) -> None:
        if self.note is not None:
            self.note.setStyleSheet(
                f"color:{self.pal.get('faint', '#888')};font-size:{TYPE['small']}px;")

    def restyle(self) -> None:
        self._style_note()

    def add(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)
        self.toggled_open.emit(self._expanded)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        if expanded == self._expanded and self.body.isVisible() == expanded:
            return
        self._expanded = expanded
        self.header.set_open(expanded)
        target = self.body.sizeHint().height()

        if not animate:
            self.body.setVisible(expanded)
            self.body.setMaximumHeight(16777215 if expanded else 0)
            return

        self._anim.stop()
        if expanded:
            self.body.setVisible(True)
            self.body.setMaximumHeight(0)
            self._anim.setDuration(DURATION["enter"])
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.setStartValue(0)
            self._anim.setEndValue(target)
        else:
            self._anim.setDuration(DURATION["exit"])
            self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self._anim.setStartValue(self.body.height())
            self._anim.setEndValue(0)
        self._anim.start()

    def set_badge(self, count: int) -> None:
        self.header.set_badge(count)

    # ------------------------------------------------------------- internals
    def _on_anim_done(self) -> None:
        if self._expanded:
            # Release the cap so the body can grow when its contents change.
            self.body.setMaximumHeight(16777215)
        else:
            self.body.setVisible(False)
