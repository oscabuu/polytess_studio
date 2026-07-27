# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Log panel (bottom dock): colored levels, filter, per-run separators."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from polytess.gui.theme import ACCENTS, COLORS

_LEVELS = ["debug", "info", "warning", "error"]
_LEVEL_COLORS = {
    "debug": ACCENTS["text-light"],
    "info": ACCENTS["text"],
    "warning": ACCENTS["yellow"],
    "error": ACCENTS["red"],
}


class LogPanel(QWidget):

    message = Signal(str, str)   # thread-safe entry point (level, text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_level = 0
        self._entries: list[tuple[str, str, str]] = []   # (time, level, text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(4, 3, 4, 3)
        self.filter_box = QComboBox()
        self.filter_box.addItems([lvl.capitalize() for lvl in _LEVELS])
        self.filter_box.currentIndexChanged.connect(self._set_filter)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        bar.addWidget(self.filter_box)
        bar.addStretch(1)
        bar.addWidget(clear_btn)
        layout.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(20000)
        self.view.setStyleSheet(
            f"QPlainTextEdit {{ background: {COLORS['bg-darkest']};"
            f" border: none; font-family: Menlo, Consolas, monospace; }}")
        layout.addWidget(self.view, 1)

        self.message.connect(self._append)

    # ---- API ----------------------------------------------------------------- #

    def log(self, level: str, text: str) -> None:
        """Callable from any coroutine/callback; marshals via signal."""
        self.message.emit(level, text)

    def separator(self, title: str) -> None:
        self.message.emit("info", f"───── {title} ─────")

    def clear(self) -> None:
        self._entries.clear()
        self.view.clear()

    # ---- internals -------------------------------------------------------------- #

    def _set_filter(self, index: int) -> None:
        self._min_level = index
        self.view.clear()
        for stamp, level, text in self._entries:
            if _LEVELS.index(level) >= self._min_level:
                self._write(stamp, level, text)

    def _append(self, level: str, text: str) -> None:
        level = level if level in _LEVELS else "info"
        stamp = time.strftime("%H:%M:%S")
        self._entries.append((stamp, level, text))
        if _LEVELS.index(level) >= self._min_level:
            self._write(stamp, level, text)

    def _write(self, stamp: str, level: str, text: str) -> None:
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(ACCENTS["text-light"]))
        cursor.insertText(f"{stamp}  ", fmt)
        fmt.setForeground(QColor(_LEVEL_COLORS[level]))
        cursor.insertText(f"{level.upper():7s} ", fmt)
        fmt.setForeground(QColor(_LEVEL_COLORS[level] if level != "info" else ACCENTS["text"]))
        cursor.insertText(text + "\n", fmt)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()
