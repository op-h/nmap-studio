"""Palettes, fonts and the application stylesheet, built from design tokens."""
from __future__ import annotations

import os

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette

from .design import RADIUS, SPACE, TRACKING_CAPS, TYPE, scaled

# --------------------------------------------------------------------------
# palettes
#
# One accent carries the whole interface. Green/amber/red mean a port state and
# nothing else, so colour always answers "what is this", never "look here".
# --------------------------------------------------------------------------

DARK = {
    "bg": "#0c0f14", "surface": "#12161d", "surface2": "#171c25", "raised": "#1d242f",
    "line": "#222a36", "line_soft": "#192029", "overlay": "#151b23",
    "text": "#e8edf4", "dim": "#98a5b4", "faint": "#748294",
    "accent": "#3d8bfd", "accent_text": "#ffffff", "accent_dim": "#1e3a5f",
    "open": "#3fb950", "closed": "#f85149", "filtered": "#d29922",
    "purple": "#a371f7", "cyan": "#39c5cf",
    "term_bg": "#090c11", "shadow": "#000000",
}

LIGHT = {
    "bg": "#eef1f5", "surface": "#ffffff", "surface2": "#f4f6f9", "raised": "#e8ecf2",
    "line": "#d5dce5", "line_soft": "#e6eaf0", "overlay": "#ffffff",
    "text": "#141a21", "dim": "#5b6875", "faint": "#5f6c79",
    "accent": "#0b69d4", "accent_text": "#ffffff", "accent_dim": "#cfe2fb",
    "open": "#1a7f37", "closed": "#cf222e", "filtered": "#9a6700",
    "purple": "#8250df", "cyan": "#1b7c83",
    "term_bg": "#0c1016", "shadow": "#8a94a6",
}


def palette_for(name: str, accent: str | None = None) -> dict:
    pal = dict(LIGHT if name == "light" else DARK)
    pal["mode"] = name
    if accent:
        colour = QColor(accent)
        pal["accent"] = colour.name()
        pal["accent_text"] = "#ffffff" if colour.lightness() < 150 else "#0b1117"
        pal["accent_dim"] = _mix(colour.name(), pal["surface"], 0.28)
    return pal


# --------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------

def mono_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("JetBrains Mono", "Fira Code", "Cascadia Code", "Hack",
                      "Source Code Pro", "Ubuntu Mono", "DejaVu Sans Mono",
                      "Liberation Mono", "Monospace"):
        if candidate in families:
            return candidate
    return "monospace"


def ui_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("Inter", "SF Pro Text", "Segoe UI", "Cantarell", "Ubuntu",
                      "Noto Sans", "DejaVu Sans"):
        if candidate in families:
            return candidate
    return "sans-serif"


def tabular(font: QFont) -> QFont:
    """Lock digits to equal width so timers and counters stop jittering."""
    out = QFont(font)
    try:                                     # Qt 6.7+ exposes OpenType features
        out.setFeature(QFont.Tag("tnum"), 1)
        out.setFeature(QFont.Tag("lnum"), 1)
    except (AttributeError, TypeError):      # older Qt: monospace digits instead
        out.setFamily(mono_family())
    return out


def numeric_font(point_size: float, weight: int = 600) -> QFont:
    font = QFont(ui_family())
    font.setPointSizeF(point_size)
    font.setWeight(QFont.Weight(weight))
    return tabular(font)


# --------------------------------------------------------------------------
# Qt palette (menus, tooltips, native dialogs)
# --------------------------------------------------------------------------

def qt_palette(pal: dict) -> QPalette:
    qp = QPalette()
    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    qp.setColor(role.Window, QColor(pal["bg"]))
    qp.setColor(role.WindowText, QColor(pal["text"]))
    qp.setColor(role.Base, QColor(pal["surface"]))
    qp.setColor(role.AlternateBase, QColor(pal["surface2"]))
    qp.setColor(role.Text, QColor(pal["text"]))
    qp.setColor(role.Button, QColor(pal["surface2"]))
    qp.setColor(role.ButtonText, QColor(pal["text"]))
    qp.setColor(role.Highlight, QColor(pal["accent"]))
    qp.setColor(role.HighlightedText, QColor(pal["accent_text"]))
    qp.setColor(role.ToolTipBase, QColor(pal["overlay"]))
    qp.setColor(role.ToolTipText, QColor(pal["text"]))
    qp.setColor(role.PlaceholderText, QColor(pal["faint"]))
    qp.setColor(role.Link, QColor(pal["accent"]))
    for state in (group.Disabled,):
        qp.setColor(state, role.Text, QColor(pal["faint"]))
        qp.setColor(state, role.ButtonText, QColor(pal["faint"]))
        qp.setColor(state, role.WindowText, QColor(pal["faint"]))
    return qp


# --------------------------------------------------------------------------
# stylesheet
# --------------------------------------------------------------------------

def stylesheet(pal: dict, font_size: int = 10, mono_size: int = 10) -> str:
    scale = font_size / 10
    mono_scale = mono_size / 10
    tokens = dict(pal)
    tokens.update({
        "ui_font": ui_family(),
        "mono_font": mono_family(),
        # type scale
        "fs_micro": scaled(TYPE["micro"], scale),
        "fs_small": scaled(TYPE["small"], scale),
        "fs_body": scaled(TYPE["body"], scale),
        "fs_medium": scaled(TYPE["medium"], scale),
        "fs_title": scaled(TYPE["title"], scale),
        "fs_mono": scaled(TYPE["body"], mono_scale),
        # radii
        "r_chip": RADIUS["chip"], "r_control": RADIUS["control"],
        "r_panel": RADIUS["panel"], "r_card": RADIUS["card"],
        # spacing
        "s_xs": SPACE["xs"], "s_sm": SPACE["sm"], "s_md": SPACE["md"],
        "s_lg": SPACE["lg"], "s_xl": SPACE["xl"],
        # derived colours
        "accent_soft": _mix(pal["accent"], pal["surface"], 0.16),
        "accent_hover": _shift(pal["accent"], 1.12),
        "accent_press": _shift(pal["accent"], 0.9),
        "row_hover": _mix(pal["text"], pal["surface"], 0.05),
        "sel_soft": _mix(pal["accent"], pal["surface"], 0.20),
        "track": _mix(pal["text"], pal["surface"], 0.10),
        # control metrics — keeps every hit area at least 30px tall
        "ctl_h": scaled(30, max(scale, 1.0)),
        "ctl_pad_v": scaled(6, scale),
        "ctl_pad_h": scaled(10, scale),
        "tick_icon": tick_icon_path(pal),
    })
    return _QSS % tokens


def tick_icon_path(pal: dict) -> str:
    """A checkmark PNG for the checked checkbox, written where QSS can load it.

    Qt stylesheets cannot draw, so a checked box would otherwise be a solid
    block of accent colour with no tick in it.
    """
    from PyQt6.QtCore import QStandardPaths
    from . import icons

    cache = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation) or "/tmp"
    folder = os.path.join(cache, "nmapgui")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"tick-{pal['accent_text'].lstrip('#')}.png")
    if not os.path.isfile(path):
        icons.icon("tick", pal["accent_text"], 14).pixmap(14, 14).save(path, "PNG")
    return path.replace("\\", "/")


def _shift(hex_colour: str, factor: float) -> str:
    c = QColor(hex_colour)
    hue = c.hueF() if c.hueF() >= 0 else 0.0
    return QColor.fromHsvF(hue, c.saturationF(), min(1.0, c.valueF() * factor)).name()


def _mix(a: str, b: str, ratio: float) -> str:
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() * ratio + cb.red() * (1 - ratio)),
                  int(ca.green() * ratio + cb.green() * (1 - ratio)),
                  int(ca.blue() * ratio + cb.blue() * (1 - ratio))).name()


_QSS = """
* { outline: 0; }

/* No background on the universal rule: a plain QWidget or QLabel inside a card
   would otherwise paint the window colour straight over it. Surfaces opt in. */
QWidget {
    color: %(text)s;
    font-family: "%(ui_font)s";
    font-size: %(fs_body)dpx;
}
QMainWindow, QDialog, QDockWidget { background: %(bg)s; }
QLabel, QSplitter, QStackedWidget, QTabWidget { background: transparent; }

QToolTip {
    background: %(overlay)s;
    color: %(text)s;
    border: 1px solid %(line)s;
    border-radius: %(r_control)dpx;
    padding: %(s_sm)dpx %(s_md)dpx;
    font-size: %(fs_small)dpx;
}

/* ------------------------------------------------------------------ menus */
QMenuBar { background: %(surface)s; border-bottom: 1px solid %(line)s; padding: 3px %(s_sm)dpx; }
QMenuBar::item { padding: 5px %(s_lg)dpx; border-radius: %(r_chip)dpx; background: transparent; }
QMenuBar::item:selected { background: %(raised)s; }
QMenuBar::item:pressed { background: %(accent_soft)s; }

QMenu {
    background: %(overlay)s; border: 1px solid %(line)s;
    border-radius: %(r_panel)dpx; padding: %(s_xs)dpx;
}
QMenu::item { padding: 6px %(s_xl)dpx 6px %(s_lg)dpx; border-radius: %(r_chip)dpx; min-height: 20px; }
QMenu::item:selected { background: %(accent)s; color: %(accent_text)s; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(line)s; margin: %(s_xs)dpx %(s_md)dpx; }
QMenu::icon { padding-left: %(s_md)dpx; }

/* --------------------------------------------------------------- toolbars */
QToolBar {
    background: %(surface)s; border: 0;
    border-bottom: 1px solid %(line)s;
    padding: %(s_md)dpx %(s_lg)dpx; spacing: %(s_md)dpx;
}
QToolBar QLabel { color: %(dim)s; font-size: %(fs_small)dpx; }
QToolButton {
    background: transparent; border: 1px solid transparent;
    border-radius: %(r_control)dpx; padding: 5px 7px; color: %(text)s;
    min-width: 22px; min-height: 22px;
}
QToolButton:hover { background: %(raised)s; }
QToolButton:pressed { background: %(surface2)s; }
QToolButton:checked { background: %(accent_soft)s; border-color: %(accent)s; }
QToolButton:disabled { color: %(faint)s; }

/* ---------------------------------------------------------------- buttons */
QPushButton {
    background: %(surface2)s; border: 1px solid %(line)s;
    border-radius: %(r_control)dpx;
    padding: %(ctl_pad_v)dpx %(ctl_pad_h)dpx;
    color: %(text)s; font-weight: 500; min-height: 18px;
}
QPushButton:hover { background: %(raised)s; border-color: %(faint)s; }
QPushButton:pressed { background: %(surface)s; }
QPushButton:focus { border-color: %(accent)s; }
QPushButton:disabled { color: %(faint)s; background: %(surface)s; border-color: %(line_soft)s; }

QPushButton[accent="true"] {
    background: %(accent)s; color: %(accent_text)s;
    border: 1px solid %(accent)s; font-weight: 600;
}
QPushButton[accent="true"]:hover { background: %(accent_hover)s; border-color: %(accent_hover)s; }
QPushButton[accent="true"]:pressed { background: %(accent_press)s; }
QPushButton[accent="true"]:disabled { background: %(surface2)s; color: %(faint)s; border-color: %(line)s; }

QPushButton[danger="true"] { border-color: %(line)s; color: %(closed)s; }
QPushButton[danger="true"]:hover { background: %(closed)s; color: #ffffff; border-color: %(closed)s; }
QPushButton[danger="true"]:disabled { color: %(faint)s; border-color: %(line_soft)s; background: %(surface)s; }

QPushButton[flat="true"] { background: transparent; border-color: transparent; color: %(dim)s; }
QPushButton[flat="true"]:hover { background: %(raised)s; color: %(text)s; }
QPushButton[flat="true"]:checked { background: %(accent_soft)s; color: %(text)s; }

/* ----------------------------------------------------------------- inputs */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox, QAbstractSpinBox {
    background: %(surface2)s; border: 1px solid %(line)s;
    border-radius: %(r_control)dpx;
    padding: %(ctl_pad_v)dpx %(ctl_pad_h)dpx;
    selection-background-color: %(accent)s; selection-color: %(accent_text)s;
    min-height: 18px;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: %(faint)s; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QComboBox:focus { border-color: %(accent)s; background: %(surface)s; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
    color: %(faint)s; background: %(surface)s; border-color: %(line_soft)s;
}
QLineEdit[mono="true"], QPlainTextEdit[mono="true"], QTextEdit[mono="true"] {
    font-family: "%(mono_font)s"; font-size: %(fs_mono)dpx;
}
QLineEdit[custom="true"] { border-color: %(filtered)s; }

/* a line edit that lives inside an IconField: the frame draws the border */
QFrame[role="field"] {
    background: %(surface2)s; border: 1px solid %(line)s;
    border-radius: %(r_control)dpx; min-height: %(ctl_h)dpx;
}
QFrame[role="field"]:hover { border-color: %(faint)s; }
QFrame[role="field"][focused="true"] { border-color: %(accent)s; background: %(surface)s; }
QFrame[role="field"][custom="true"] { border-color: %(filtered)s; }
QLineEdit[inField="true"] {
    background: transparent; border: 0; border-radius: 0;
    padding: 0; min-height: 0;
}

/* a visible tick, not just a filled square */
QCheckBox::indicator:checked { image: url(%(tick_icon)s); }

QComboBox::drop-down { border: 0; width: 20px; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox QAbstractItemView {
    background: %(overlay)s; border: 1px solid %(line)s;
    border-radius: %(r_panel)dpx; padding: %(s_xs)dpx;
    selection-background-color: %(accent)s; selection-color: %(accent_text)s;
    outline: 0;
}
QSpinBox::up-button, QSpinBox::down-button { width: 14px; border: 0; background: transparent; }
QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; width: 0; height: 0; }

/* ------------------------------------------------------ checks and radios */
QCheckBox, QRadioButton { spacing: %(s_md)dpx; padding: 3px 0; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid %(faint)s; background: %(surface2)s;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: %(accent)s; border-color: %(accent)s;
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    border-color: %(line)s; background: %(surface)s;
}
QCheckBox:disabled, QRadioButton:disabled { color: %(faint)s; }

/* ------------------------------------------------------------------- tabs */
QTabWidget::pane { border: 0; background: transparent; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent; color: %(dim)s;
    padding: %(s_md)dpx %(s_lg)dpx; margin-right: 2px;
    border: 0; border-bottom: 2px solid transparent;
    font-size: %(fs_medium)dpx;
}
QTabBar::tab:hover { color: %(text)s; }
QTabBar::tab:selected { color: %(text)s; border-bottom-color: %(accent)s; font-weight: 600; }
QTabBar::tab:disabled { color: %(faint)s; }
QTabBar::close-button { image: none; background: transparent; width: 14px; height: 14px; }
QTabBar::close-button:hover { background: %(closed)s; border-radius: 7px; }

/* ------------------------------------------------------ lists and tables */
QTreeWidget, QTreeView, QTableWidget, QTableView, QListWidget, QListView {
    background: %(surface)s; border: 1px solid %(line)s;
    border-radius: %(r_panel)dpx;
    alternate-background-color: %(surface2)s;
    selection-background-color: %(sel_soft)s; selection-color: %(text)s;
    gridline-color: %(line_soft)s;
    outline: 0;
}
QTreeView::item, QTableView::item, QListView::item {
    padding: 5px %(s_sm)dpx; border: 0; min-height: 20px;
}
QTreeView::item:hover, QTableView::item:hover, QListView::item:hover { background: %(row_hover)s; }
QTreeView::item:selected, QTableView::item:selected, QListView::item:selected {
    background: %(sel_soft)s; color: %(text)s;
}
QHeaderView { background: transparent; }
QHeaderView::section {
    background: %(surface2)s; color: %(dim)s; border: 0;
    border-bottom: 1px solid %(line)s;
    padding: 7px %(s_md)dpx;
    font-size: %(fs_micro)dpx; font-weight: 600;
    text-transform: uppercase;
}
QHeaderView::section:hover { color: %(text)s; background: %(raised)s; }
QTableCornerButton::section { background: %(surface2)s; border: 0; }

/* -------------------------------------------------------------- scrollbar */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: %(track)s; border-radius: 4px; min-height: 28px; min-width: 28px;
}
QScrollBar::handle:hover { background: %(faint)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ----------------------------------------------------------------- groups */
QGroupBox {
    border: 1px solid %(line)s; border-radius: %(r_card)dpx;
    margin-top: %(s_xl)dpx; padding: %(s_xl)dpx %(s_lg)dpx %(s_lg)dpx %(s_lg)dpx;
    background: %(surface)s;
}
QGroupBox::title {
    subcontrol-origin: margin; left: %(s_lg)dpx; padding: 0 %(s_sm)dpx;
    color: %(dim)s; font-weight: 600; font-size: %(fs_micro)dpx;
}

/* --------------------------------------------------------------- progress */
QProgressBar {
    background: %(track)s; border: 0; border-radius: 3px;
    height: 6px; text-align: center; color: %(dim)s;
}
QProgressBar::chunk { border-radius: 3px; background: %(accent)s; }

/* --------------------------------------------------------------- splitter */
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: %(s_md)dpx; }
QSplitter::handle:vertical { height: %(s_md)dpx; }
QSplitter::handle:hover { background: %(accent_soft)s; }

/* -------------------------------------------------------------- statusbar */
QStatusBar { background: %(surface)s; border-top: 1px solid %(line)s; color: %(dim)s; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { color: %(dim)s; font-size: %(fs_small)dpx; }

/* ------------------------------------------------------------------- dock */
QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
QDockWidget::title {
    background: %(surface)s; padding: %(s_md)dpx %(s_lg)dpx;
    border-bottom: 1px solid %(line)s; text-align: left;
    font-size: %(fs_micro)dpx; font-weight: 700; color: %(dim)s;
}

/* ------------------------------------------------------------------ roles */
QLabel[role="eyebrow"] {
    color: %(dim)s; font-size: %(fs_micro)dpx; font-weight: 700;
}
QLabel[role="title"] { color: %(text)s; font-size: %(fs_title)dpx; font-weight: 600; }
QLabel[role="dim"] { color: %(dim)s; font-size: %(fs_small)dpx; }
QLabel[role="faint"] { color: %(faint)s; font-size: %(fs_small)dpx; }
QLabel[role="mono"] { font-family: "%(mono_font)s"; font-size: %(fs_mono)dpx; }

QFrame[role="card"] {
    background: %(surface)s; border: 1px solid %(line)s; border-radius: %(r_card)dpx;
}
QFrame[role="panel"] {
    background: %(surface)s; border: 1px solid %(line)s; border-radius: %(r_panel)dpx;
}
QFrame[role="sep"] { background: %(line)s; max-height: 1px; border: 0; }
QFrame[role="vsep"] { background: %(line)s; max-width: 1px; border: 0; }

QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QTextBrowser { background: %(surface)s; border: 1px solid %(line)s; border-radius: %(r_panel)dpx; }
"""
