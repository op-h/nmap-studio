"""Shared building blocks: cards, stat blocks, animated numerals, toasts."""
from __future__ import annotations

from PyQt6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt,
                          QTimer, QVariantAnimation, pyqtSignal)
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                             QHBoxLayout, QLabel, QLayout, QLineEdit, QSizePolicy,
                             QVBoxLayout, QWidget)

from .. import icons
from ..design import DURATION, ELEVATION, RADIUS, SPACE, TYPE
from ..theme import numeric_font


def restyle_tree(root: QWidget) -> None:
    """Re-apply inline styling after the palette changes.

    Every widget shares the one palette dict, which is mutated in place on a
    theme switch, so a widget only has to re-run the styling it set itself.
    """
    for child in root.findChildren(QWidget):
        hook = getattr(child, "restyle", None)
        if callable(hook):
            hook()


def elevate(widget: QWidget, level: str = "raised", pal: dict | None = None) -> QWidget:
    """Attach a soft shadow. Borders separate; shadows are only for floating things."""
    dx, dy, blur, alpha = ELEVATION[level]
    effect = QGraphicsDropShadowEffect(widget)
    effect.setXOffset(dx)
    effect.setYOffset(dy)
    effect.setBlurRadius(blur)
    colour = QColor(pal["shadow"] if pal else "#000000")
    colour.setAlpha(alpha)
    effect.setColor(colour)
    widget.setGraphicsEffect(effect)
    return widget


def fade_in(widget: QWidget, duration: int = DURATION["enter"]) -> None:
    """A short opacity lift on appearance. Enter is slower than exit, on purpose."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    widget._fade_anim = anim  # keep a reference alive


class FlowLayout(QLayout):
    """Lays items out left to right and wraps to the next line when it runs out
    of width. Qt has no flow layout, and a row of stat cards has to wrap rather
    than run off the edge of a narrow window."""

    def __init__(self, parent=None, spacing: int = SPACE["lg"]):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:          # noqa: N802  (Qt override)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):                  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):                  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):            # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:      # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:   # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:      # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:              # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:           # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(),
                            margins.top() + margins.bottom())

    def _layout(self, rect: QRect, apply: bool) -> int:
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        right = rect.right() - margins.right()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            if x > rect.x() + margins.left() and x + hint.width() > right:
                x = rect.x() + margins.left()
                y += line_height + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class IconField(QFrame):
    """A line edit with a leading icon, laid out as one control.

    QLineEdit.addAction() puts the icon in the widget's content rect, which
    does not line up with the text once the field has custom padding and a
    minimum height — it sat low and clipped. Owning the layout fixes it, and
    the frame carries the border so the icon lives inside the control.
    """

    def __init__(self, icon_name: str, pal: dict, parent=None, mono: bool = False):
        super().__init__(parent)
        self.pal = pal
        self._icon_name = icon_name
        self.setProperty("role", "field")
        self.setProperty("focused", "false")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], 0, SPACE["sm"], 0)
        layout.setSpacing(SPACE["sm"])

        self.glyph = QLabel(self)
        self.glyph.setFixedSize(16, 16)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignVCenter)

        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        self.edit.setProperty("inField", "true")
        if mono:
            self.edit.setProperty("mono", "true")
        self.edit.setClearButtonEnabled(True)
        self.edit.installEventFilter(self)
        layout.addWidget(self.edit, 1)

        self.setFocusProxy(self.edit)
        self.restyle()

    # Everything the call sites use — placeholder, text, signals — belongs to
    # the inner editor, so anything this frame does not define is forwarded.
    def __getattr__(self, name):
        try:
            edit = self.__dict__["edit"]
        except KeyError:
            raise AttributeError(name) from None
        return getattr(edit, name)

    def restyle(self) -> None:
        self.glyph.setPixmap(
            icons.icon(self._icon_name, self.pal["faint"], 16).pixmap(16, 16))

    def set_icon(self, name: str) -> None:
        self._icon_name = name
        self.restyle()

    def eventFilter(self, obj, event):
        if obj is self.edit and event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self.setProperty("focused",
                             "true" if event.type() == event.Type.FocusIn else "false")
            self.style().unpolish(self)
            self.style().polish(self)
        return super().eventFilter(obj, event)


class Card(QFrame):
    def __init__(self, pal: dict, parent=None, padding: int = SPACE["xl"], panel: bool = False):
        super().__init__(parent)
        self.pal = pal
        self.setProperty("role", "panel" if panel else "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(SPACE["lg"])

    def body(self) -> QVBoxLayout:
        return self._layout


class Eyebrow(QLabel):
    """Uppercase micro label. Needs tracking or it reads as a smudge."""

    def __init__(self, text: str, pal: dict, parent=None):
        super().__init__(text.upper(), parent)
        self.pal = pal
        self.setProperty("role", "eyebrow")
        font = self.font()
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)
        self.restyle()

    def restyle(self) -> None:
        self.setStyleSheet(f"color:{self.pal['faint']};")


class AnimatedNumber(QLabel):
    """A counter that rolls up to its value instead of snapping."""

    def __init__(self, pal: dict, size: int = TYPE["display"], colour: str | None = None,
                 parent=None):
        super().__init__("0", parent)
        self.pal = pal
        self._value = 0.0
        self._suffix = ""
        self._decimals = 0
        self._colour_key = colour
        self.setFont(numeric_font(size * 0.75, 700))
        self.restyle()
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(DURATION["slow"])
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_step)

    def restyle(self) -> None:
        self.setStyleSheet(f"color:{self._colour_key or self.pal['text']};")

    def set_value(self, value: float, suffix: str = "", decimals: int = 0,
                  animate: bool = True) -> None:
        self._suffix = suffix
        self._decimals = decimals
        target = float(value)
        if not animate or abs(target - self._value) < 0.5:
            self._value = target
            self._render(target)
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._value))
        self._anim.setEndValue(target)
        self._value = target
        self._anim.start()

    def _on_step(self, value) -> None:
        self._render(float(value))

    def _render(self, value: float) -> None:
        text = f"{value:.{self._decimals}f}" if self._decimals else f"{int(round(value))}"
        self.setText(text + self._suffix)


class StatBlock(QWidget):
    """Eyebrow label over a value. The unit of measurement across the app."""

    def __init__(self, label: str, pal: dict, value: str = "—", colour: str | None = None,
                 size: int = TYPE["medium"], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.caption = Eyebrow(label, pal, self)
        layout.addWidget(self.caption)
        self.pal = pal
        self._colour = colour
        self.value = QLabel(value, self)
        self.value.setFont(numeric_font(size * 0.82, 600))
        self.restyle()
        layout.addWidget(self.value)

    def restyle(self) -> None:
        self.value.setStyleSheet(f"color:{self._colour or self.pal['text']};")

    def set_value(self, text: str, colour: str | None = None) -> None:
        self.value.setText(text)
        if colour:
            self._colour = colour
        self.restyle()


class PulseDot(QWidget):
    """A slow breathing dot. The only thing in the app allowed to loop forever,
    and only while a scan is actually running."""

    def __init__(self, pal: dict, colour: str | None = None, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._colour = QColor(colour or pal["accent"])
        self._phase = 0.6
        self.setFixedSize(10, 10)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(1400)
        self._anim.setStartValue(0.30)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.valueChanged.connect(self._on_step)
        self._anim.finished.connect(self._bounce)
        self._forward = True

    def _on_step(self, value) -> None:
        self._phase = float(value)
        self.update()

    def _bounce(self) -> None:
        if not self.isVisible():
            return
        self._forward = not self._forward
        self._anim.setDirection(QVariantAnimation.Direction.Backward if not self._forward
                                else QVariantAnimation.Direction.Forward)
        self._anim.start()

    def start(self, colour: str | None = None) -> None:
        if colour:
            self._colour = QColor(colour)
        self.show()
        if self._anim.state() != QVariantAnimation.State.Running:
            self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        self.hide()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        halo = QColor(self._colour)
        halo.setAlphaF(0.20 * self._phase)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(self.rect())
        core = QColor(self._colour)
        core.setAlphaF(0.55 + 0.45 * self._phase)
        painter.setBrush(core)
        painter.drawEllipse(self.rect().adjusted(3, 3, -3, -3))


class EmptyState(QWidget):
    """A designed empty state: icon, one line of what goes here, one of how."""

    def __init__(self, icon_name: str, title: str, hint: str, pal: dict, parent=None):
        super().__init__(parent)
        self.pal = pal
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["3xl"], SPACE["3xl"], SPACE["3xl"], SPACE["3xl"])
        layout.setSpacing(SPACE["md"])
        layout.addStretch(1)

        self.glyph = QLabel(self)
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.glyph)

        self.head = QLabel(title, self)
        self.head.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.head)

        # A wrapped QLabel added with an alignment flag gets its sizeHint height,
        # not its heightForWidth, and silently loses the last lines. Giving it a
        # fixed width inside a centring row makes the wrap height correct.
        self.sub = QLabel(hint, self)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.sub.setWordWrap(True)
        self.sub.setFixedWidth(320)
        self.sub.setMinimumHeight(self.sub.fontMetrics().boundingRect(
            0, 0, 320, 400, int(Qt.TextFlag.TextWordWrap), hint).height() + 4)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self.sub)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        self.restyle()

    def restyle(self) -> None:
        pal = self.pal
        self.glyph.setPixmap(icons.icon(self._icon_name, pal["faint"], 34).pixmap(34, 34))
        self.head.setStyleSheet(
            f"color:{pal['dim']};font-size:{TYPE['medium']}px;font-weight:600;")
        self.sub.setStyleSheet(f"color:{pal['faint']};font-size:{TYPE['small']}px;")


class Toast(QFrame):
    """A short-lived message near the bottom of the window. Enters with a small
    rise, leaves faster than it arrived, and never blocks anything."""

    dismissed = pyqtSignal()

    def __init__(self, message: str, pal: dict, kind: str = "info", parent=None,
                 timeout: int = 4200):
        super().__init__(parent)
        self.pal = pal
        colour = {"info": pal["accent"], "good": pal["open"],
                  "warn": pal["filtered"], "bad": pal["closed"]}.get(kind, pal["accent"])
        self.setStyleSheet(
            f"QFrame{{background:{pal['overlay']};border:1px solid {pal['line']};"
            f"border-left:3px solid {colour};border-radius:{RADIUS['panel']}px;}}")
        elevate(self, "toast", pal)

        layout = QHBoxLayout(self)
        # +3 on the left so the content clears the accent border, not sits on it.
        layout.setContentsMargins(SPACE["lg"] + 3, SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["md"])

        glyph = QLabel(self)
        name = {"good": "check", "warn": "warning", "bad": "warning"}.get(kind, "info")
        glyph.setPixmap(icons.icon(name, colour, 16).pixmap(16, 16))
        glyph.setFixedWidth(16)
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

        text = QLabel(message, self)
        text.setWordWrap(len(message) > 58)
        if text.wordWrap():
            text.setFixedWidth(340)
        text.setStyleSheet(f"color:{pal['text']};font-size:{TYPE['body']}px;")
        layout.addWidget(text, 1)

        self.setMaximumWidth(420)
        self.adjustSize()
        # Word wrap only settles the height once the width is known.
        self.setFixedHeight(self.sizeHint().height())
        # A widget can hold only one QGraphicsEffect, and this one is using the
        # drop shadow, so the toast animates its position rather than opacity.
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(DURATION["enter"])
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        QTimer.singleShot(timeout, self.dismiss)

    def show_at(self, x: int, y: int) -> None:
        self.move(x, y + 14)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setDuration(DURATION["enter"])
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos() - QPoint(0, 14))
        self._anim.start()

    def dismiss(self) -> None:
        self._anim.stop()
        self._anim.setDuration(DURATION["exit"])
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos() + QPoint(0, 10))
        self._anim.finished.connect(self._finish)
        self._anim.start()

    def _finish(self) -> None:
        self.dismissed.emit()
        self.deleteLater()
