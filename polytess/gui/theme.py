# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Dark theme — color/measure tokens taken 1:1 from 
(CommonColors_Dark.uss + ColorTheme.cs) plus the application stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor

# ---- CommonColors_Dark.uss -------------------------------------------- #

COLORS = {
    "bg-default": "#383838",
    "bg-dark": "#333333",
    "bg-darker": "#2a2a2a",
    "bg-darkest": "#191919",
    "bg-light": "#3f3f3f",
    "bg-lighter": "#494949",
    "bg-lightest": "#565656",
    "border-default": "#1a1a1a",
    "border-element": "#303030",
    "border-hover": "#656565",
    "border-active": "#3d7ad9",
    "bg-active": "#2e5e85",
    "accept": "#519932",
    "warning": "#b0963a",
    "error": "#b03a3a",
    "list-head": "#404040",
    "list-head-hover": "#545454",
    "list-head-press": "#333333",
    "list-head-expanded": "#2a2a2a",
    "list-head-running": "#191919",
    "list-body": "#333333",
    "canvas": "#262626",
    "grid-minor": "#2d2d2d",
    "grid-major": "#212121",
}

# ---- ColorTheme accents (dark skin) ------------------------------------ #

ACCENTS = {
    "text": "#ffffff",
    "text-light": "#aaaaaa",
    "red": "#e9754c",
    "green": "#c2f771",
    "blue": "#87d8f6",
    "yellow": "#f1c437",
    "purple": "#a692e9",
    "pink": "#d790d4",
    "teal": "#a2f7e4",
}

# Node title-bar colors
NODE_ACCENTS = {
    "purple": "#3d2679",
    "blue": "#1f4e63",
    "green": "#2e5b2a",
    "red": "#662019",
    "yellow": "#6b571a",
    "teal": "#1d5a4e",
}

# ---- CommonValues.uss --------------------------------------------------- #

ROW_HEIGHT = 22
ICON_SIZE = 16
BORDER_RADIUS = 3
INDENT = 10
SPACING = 5

STATUS_COLORS = {
    "running": "#3d7ad9",
    "success": "#519932",
    "fail": "#b03a3a",
    "paused": "#f1c437",
}


def qcolor(token: str) -> QColor:
    return QColor(COLORS.get(token) or ACCENTS.get(token) or token)


def accent(token: str) -> QColor:
    return QColor(ACCENTS.get(token, ACCENTS["text"]))


def node_accent(token: str) -> QColor:
    return QColor(NODE_ACCENTS.get(token, NODE_ACCENTS["blue"]))


def darker(color: QColor, factor: float = 0.15) -> QColor:
    h, s, v, a = color.getHsvF()
    return QColor.fromHsvF(h, s, max(0.0, v - factor), a)


def lighter(color: QColor, factor: float = 0.15) -> QColor:
    h, s, v, a = color.getHsvF()
    return QColor.fromHsvF(h, s, min(1.0, v + factor), a)


def _combo_arrow_url() -> str:
    """Small ▼ pixmap for QComboBox (QSS needs an image url); cached on disk."""
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "polytess-combo-arrow.png")
    if not os.path.exists(path):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QPainter, QPixmap, QPolygonF
        pixmap = QPixmap(8, 8)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ACCENTS["text-light"]))
        painter.drawPolygon(QPolygonF([QPointF(0.5, 2.0), QPointF(7.5, 2.0),
                                       QPointF(4.0, 6.5)]))
        painter.end()
        pixmap.save(path)
    return path.replace(os.sep, "/")


def build_qss() -> str:
    c = dict(COLORS)
    c.update({f"accent-{k}": v for k, v in ACCENTS.items()})
    return f"""
QWidget {{
    background-color: {c['bg-default']};
    color: {ACCENTS['text']};
    font-size: 12px;
}}
QMainWindow::separator {{
    background: {c['border-default']};
    width: 3px; height: 3px;
}}
QMenuBar {{ background-color: {c['bg-dark']}; border-bottom: 1px solid {c['border-default']}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {c['bg-lighter']}; }}
QMenu {{
    background-color: {c['bg-dark']};
    border: 1px solid {c['border-default']};
    padding: 3px;
}}
QMenu::item {{ padding: 4px 24px 4px 12px; border-radius: 2px; }}
QMenu::item:selected {{ background: {c['bg-active']}; }}
QMenu::separator {{ height: 1px; background: {c['border-element']}; margin: 3px 6px; }}
QToolBar {{
    background: {c['bg-dark']};
    border-bottom: 1px solid {c['border-default']};
    spacing: 3px; padding: 3px;
}}
QToolButton {{
    background: transparent; border: 1px solid transparent;
    border-radius: {BORDER_RADIUS}px; padding: 3px;
}}
QToolButton:hover {{ background: {c['bg-lighter']}; border-color: {c['border-hover']}; }}
QToolButton:pressed {{ background: {c['list-head-press']}; }}
QToolButton:checked {{ background: {c['bg-active']}; border-color: {c['border-active']}; }}
QPushButton {{
    background-color: {c['bg-light']};
    border: 1px solid {c['border-default']};
    border-radius: {BORDER_RADIUS}px;
    padding: 3px 12px;
    min-height: 18px;
}}
QPushButton:hover {{ background-color: {c['bg-lighter']}; border-color: {c['border-hover']}; }}
QPushButton:pressed {{ background-color: {c['list-head-press']}; }}
QPushButton:disabled {{ color: {ACCENTS['text-light']}; background: {c['bg-dark']}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg-darker']};
    border: 1px solid {c['border-element']};
    border-radius: {BORDER_RADIUS}px;
    padding: 2px 5px;
    selection-background-color: {c['bg-active']};
    min-height: 18px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus {{ border-color: {c['border-active']}; }}
/* Selection menus: lighter, button-like field with a ▼ arrow.
   Editable combos keep the dark input look — the arrow marks the choices. */
QComboBox {{
    background-color: {c['bg-light']};
    border: 1px solid {c['border-default']};
    border-radius: {BORDER_RADIUS}px;
    padding: 2px 20px 2px 8px;
    selection-background-color: {c['bg-active']};
    min-height: 18px;
}}
QComboBox:hover {{ border-color: {c['border-hover']}; }}
QComboBox:editable {{
    background-color: {c['bg-darker']};
    border-color: {c['border-element']};
    padding-left: 5px;
}}
QComboBox QLineEdit {{ background: transparent; border: none; padding: 0; min-height: 0; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ image: url({_combo_arrow_url()}); width: 8px; height: 8px; }}
QComboBox QAbstractItemView {{
    background: {c['bg-dark']};
    border: 1px solid {c['border-default']};
    selection-background-color: {c['bg-active']};
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {c['border-element']};
    border-radius: 2px;
    background: {c['bg-darker']};
}}
QCheckBox::indicator:checked {{ background: {c['border-active']}; }}
QDockWidget::title {{
    background: {c['bg-dark']};
    padding: 5px 8px;
    border-bottom: 1px solid {c['border-default']};
}}
QTabWidget::pane {{ border: 1px solid {c['border-default']}; }}
QTabBar::tab {{
    background: {c['bg-dark']};
    border: 1px solid {c['border-default']};
    padding: 5px 14px;
    border-top-left-radius: {BORDER_RADIUS}px;
    border-top-right-radius: {BORDER_RADIUS}px;
}}
QTabBar::tab:selected {{ background: {c['bg-default']}; border-bottom-color: {c['bg-default']}; }}
QTabBar::tab:hover {{ background: {c['bg-lighter']}; }}
QHeaderView::section {{
    background: {c['list-head']};
    border: 1px solid {c['border-default']};
    padding: 3px 6px;
}}
QTableView, QTreeView, QListView, QListWidget, QTableWidget {{
    background: {c['bg-darker']};
    alternate-background-color: {c['bg-dark']};
    border: 1px solid {c['border-element']};
    selection-background-color: {c['bg-active']};
}}
QScrollBar:vertical {{
    background: {c['bg-dark']}; width: 12px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c['bg-lightest']}; border-radius: 4px; min-height: 24px; margin: 2px;
}}
QScrollBar:horizontal {{
    background: {c['bg-dark']}; height: 12px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c['bg-lightest']}; border-radius: 4px; min-width: 24px; margin: 2px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {c['bg-dark']}; border-top: 1px solid {c['border-default']}; }}
QToolTip {{
    background-color: {c['bg-darkest']};
    color: {ACCENTS['text']};
    border: 1px solid {c['border-hover']};
    padding: 4px;
}}
QSplitter::handle {{ background: {c['border-default']}; }}
"""
