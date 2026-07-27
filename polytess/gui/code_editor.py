# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""In-studio code editor for the user library (custom instructions,
conditions and events).

Opens as a tab next to the graph documents. Files live in
``~/.polytess/custom_library``; saving syntax-checks the source, hot-reloads
the module and updates the type registry — the new building block appears
in the Add menus immediately, without restarting the studio.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QRect, QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QPainter,
                           QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                           QTextFormat)
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMenu,
                               QPlainTextEdit, QTextEdit, QToolButton,
                               QVBoxLayout, QWidget)

from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS, COLORS
from polytess.library.custom import custom_library_dir, load_custom_module

# --------------------------------------------------------------------------- #
# syntax highlighting
# --------------------------------------------------------------------------- #

_KEYWORDS = (
    "False None True and as assert async await break class continue def del "
    "elif else except finally for from global if import in is lambda nonlocal "
    "not or pass raise return try while with yield").split()


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Lightweight python highlighting in the accent palette."""

    def __init__(self, document):
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_fmt = _fmt(ACCENTS["purple"], bold=True)
        for word in _KEYWORDS:
            self._rules.append((QRegularExpression(rf"\b{word}\b"), keyword_fmt))
        self._rules.append((QRegularExpression(r"\bself\b"),
                            _fmt(ACCENTS["red"], italic=True)))
        self._rules.append((QRegularExpression(r"\b(def|class)\s+(\w+)"),
                            _fmt(ACCENTS["blue"], bold=True)))
        self._rules.append((QRegularExpression(r"@\w+(\.\w+)*"),
                            _fmt(ACCENTS["yellow"])))
        self._rules.append((QRegularExpression(
            r"\b[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b"),
            _fmt(ACCENTS["green"])))
        self._string_fmt = _fmt(ACCENTS["yellow"])
        self._rules.append((QRegularExpression(
            r"'[^'\\]*(\\.[^'\\]*)*'"), self._string_fmt))
        self._rules.append((QRegularExpression(
            r'"[^"\\]*(\\.[^"\\]*)*"'), self._string_fmt))
        self._comment_fmt = _fmt(ACCENTS["text-light"], italic=True)
        self._rules.append((QRegularExpression(r"#[^\n]*"), self._comment_fmt))
        self._triple = (QRegularExpression("'''"), QRegularExpression('"""'))

    def highlightBlock(self, text: str) -> None:   # noqa: N802 (Qt API)
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                if pattern.pattern().startswith(r"\b(def|class)"):
                    self.setFormat(match.capturedStart(2),
                                   match.capturedLength(2), fmt)
                else:
                    self.setFormat(match.capturedStart(),
                                   match.capturedLength(), fmt)
        # triple-quoted strings across blocks (state 1: ''' — state 2: """)
        self.setCurrentBlockState(0)
        start = 0
        state = self.previousBlockState()
        if state in (1, 2):
            quote = self._triple[state - 1]
            match = quote.match(text)
            if match.hasMatch():
                end = match.capturedEnd()
                self.setFormat(0, end, self._string_fmt)
                start = end
            else:
                self.setFormat(0, len(text), self._string_fmt)
                self.setCurrentBlockState(state)
                return
        while start < len(text):
            first = None
            first_state = 0
            for index, quote in enumerate(self._triple, start=1):
                match = quote.match(text, start)
                if match.hasMatch() and (first is None
                                         or match.capturedStart() < first.capturedStart()):
                    first, first_state = match, index
            if first is None:
                return
            open_at = first.capturedStart()
            close = self._triple[first_state - 1].match(text, first.capturedEnd())
            if close.hasMatch():
                self.setFormat(open_at, close.capturedEnd() - open_at,
                               self._string_fmt)
                start = close.capturedEnd()
            else:
                self.setFormat(open_at, len(text) - open_at, self._string_fmt)
                self.setCurrentBlockState(first_state)
                return


# --------------------------------------------------------------------------- #
# editor widget with line numbers
# --------------------------------------------------------------------------- #

class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEdit"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:   # noqa: N802
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:   # noqa: N802
        self._editor.paint_line_numbers(event)


class CodeEdit(QPlainTextEdit):

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(max(11, font.pointSize()))
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {COLORS['bg-darkest']};"
            f" border: 1px solid {COLORS['border-element']}; }}")
        self._numbers = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_numbers)
        self.cursorPositionChanged.connect(self._highlight_line)
        self._update_margin()
        self._highlight_line()

    # tab inserts 4 spaces (python file!)
    def keyPressEvent(self, event) -> None:   # noqa: N802
        if event.key() == Qt.Key_Tab and not event.modifiers():
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)

    # ---- line numbers ------------------------------------------------------ #

    def line_number_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_args) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_numbers(self, rect, dy) -> None:
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(),
                                 rect.height())

    def resizeEvent(self, event) -> None:   # noqa: N802
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._numbers.setGeometry(QRect(rect.left(), rect.top(),
                                        self.line_number_width(),
                                        rect.height()))

    def paint_line_numbers(self, event) -> None:
        painter = QPainter(self._numbers)
        painter.fillRect(event.rect(), QColor(COLORS["bg-dark"]))
        painter.setPen(QColor(ACCENTS["text-light"]))
        block = self.firstVisibleBlock()
        number = block.blockNumber() + 1
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                painter.drawText(0, int(top), self._numbers.width() - 6,
                                 height, Qt.AlignRight, str(number))
            top += self.blockBoundingRect(block).height()
            block = block.next()
            number += 1

    def _highlight_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(COLORS["bg-dark"]))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def go_to_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(max(0, line - 1))
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.setFocus()


# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #

_TEMPLATES = {
    "Instruction": '''"""Custom instruction — saved files load automatically at startup;
saving here hot-reloads the class (Add menu updates immediately)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetString


@meta(title="__TITLE__", category="Custom/__TITLE__", icon="terminal",
      color="teal", description="What this instruction does",
      keywords=("custom",))
class __CLASS__(Instruction):

    def __init__(self):
        super().__init__()
        self.text = PropertyGetString("hello")

    @property
    def title(self) -> str:
        return f"__TITLE__ {self.text}"

    async def run(self, ctx):
        ctx.info(f"__TITLE__: {self.text.get(ctx)}")
''',
    "Condition": '''"""Custom condition."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetNumber


@meta(title="__TITLE__", category="Custom/__TITLE__", icon="conditions",
      color="green", description="What this condition checks")
class __CLASS__(Condition):

    def __init__(self):
        super().__init__()
        self.value = PropertyGetNumber(0)

    @property
    def summary(self) -> str:
        return f"__TITLE__ {self.value}"

    def run(self, ctx) -> bool:
        return self.value.get(ctx) > 0
''',
    "Event": '''"""Custom trigger event."""

from __future__ import annotations

from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="__TITLE__", category="Custom/__TITLE__", icon="bolt", color="red",
      description="When this trigger fires")
class __CLASS__(Event):
    persistent = False      # True: keeps listening until the run stops

    def start(self, fire, ctx):
        super().start(fire, ctx)
        self.fire(None)     # fire once on workflow start
''',
}


# --------------------------------------------------------------------------- #
# the editor panel (one tab in the main window)
# --------------------------------------------------------------------------- #

class CodeEditorPanel(QWidget):

    status_message = Signal(str)

    def __init__(self, folder: str | None = None, parent=None):
        super().__init__(parent)
        self.folder = folder or custom_library_dir()
        self._path: str | None = None
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        new_button = QToolButton()
        new_button.setIcon(icon("plus", "text-light"))
        new_button.setText(" New")
        new_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        new_button.setPopupMode(QToolButton.InstantPopup)
        new_menu = QMenu(new_button)
        for kind in _TEMPLATES:
            new_menu.addAction(f"New {kind}…",
                               lambda k=kind: self._new_file(k))
        new_button.setMenu(new_menu)
        bar.addWidget(new_button)

        self.files = QComboBox()
        self.files.setMinimumWidth(240)
        self.files.currentTextChanged.connect(self._open_selected)
        bar.addWidget(self.files, 1)

        save_button = QToolButton()
        save_button.setIcon(icon("save", "text-light"))
        save_button.setToolTip("Save + reload into the registry (Ctrl+S)")
        save_button.clicked.connect(self.save)
        bar.addWidget(save_button)
        reload_button = QToolButton()
        reload_button.setIcon(icon("repeat", "text-light"))
        reload_button.setToolTip("Reload file from disk")
        reload_button.clicked.connect(self._reload_from_disk)
        bar.addWidget(reload_button)
        self.chat_button = QToolButton()
        self.chat_button.setIcon(icon("message", "teal"))
        self.chat_button.setToolTip("Claude coding assistant")
        self.chat_button.setCheckable(True)
        self.chat_button.toggled.connect(self._toggle_chat)
        bar.addWidget(self.chat_button)
        layout.addLayout(bar)

        from PySide6.QtWidgets import QSplitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.edit = CodeEdit()
        self.highlighter = PythonHighlighter(self.edit.document())
        self.edit.textChanged.connect(self._mark_dirty)
        self.splitter.addWidget(self.edit)
        self._chat = None                 # created lazily on first toggle
        layout.addWidget(self.splitter, 1)

        self.status = QLabel(f"Library folder: {self.folder}")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {ACCENTS['text-light']};")
        layout.addWidget(self.status)

        self.dirty = False
        self.refresh_files()

    # ---- files ------------------------------------------------------------- #

    def refresh_files(self, select: str | None = None) -> None:
        self._loading = True
        current = select or self.files.currentText()
        self.files.clear()
        names = sorted(n for n in os.listdir(self.folder)
                       if n.endswith(".py") and not n.startswith("_"))
        self.files.addItems(names)
        if current and current in names:
            self.files.setCurrentText(current)
        self._loading = False
        if names:
            self._open_selected(self.files.currentText())
        else:
            self.edit.setPlainText("")
            self._path = None
            self._set_status("No files yet — create one with 'New'.", ok=True)

    def _open_selected(self, name: str) -> None:
        if self._loading or not name:
            return
        path = os.path.join(self.folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            self._set_status(f"Cannot open {name}: {exc}", ok=False)
            return
        self._path = path
        self.edit.setPlainText(text)
        self.dirty = False
        self._set_status(f"{name}", ok=True)

    def _reload_from_disk(self) -> None:
        if self._path:
            self._open_selected(os.path.basename(self._path))

    def _new_file(self, kind: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(
            self, f"New {kind}", "Title (e.g. 'Copy Results'):")
        title = (title or "").strip()
        if not ok or not title:
            return
        cls = "".join(part.capitalize()
                      for part in title.replace("-", " ").split()) or "MyCustom"
        prefix = {"Instruction": "instruction_", "Condition": "condition_",
                  "Event": "event_"}[kind]
        stem = prefix + "_".join(title.lower().split())
        path = os.path.join(self.folder, f"{stem}.py")
        if os.path.exists(path):
            self._set_status(f"{os.path.basename(path)} already exists.",
                             ok=False)
            return
        source = _TEMPLATES[kind].replace("__TITLE__", title) \
                                 .replace("__CLASS__", cls)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        self.refresh_files(select=os.path.basename(path))
        self.save()

    def _mark_dirty(self) -> None:
        self.dirty = True

    def _toggle_chat(self, visible: bool) -> None:
        if self._chat is None and visible:
            from polytess.gui.code_assistant import AssistantChatPanel
            self._chat = AssistantChatPanel(editor_panel=self)
            self.splitter.addWidget(self._chat)
            self.splitter.setSizes([3 * self.width() // 5,
                                    2 * self.width() // 5])
        if self._chat is not None:
            self._chat.setVisible(visible)

    # ---- save + hot reload -------------------------------------------------- #

    def save(self) -> bool:
        if self._path is None:
            self._set_status("No file selected — create one with 'New'.",
                             ok=False)
            return False
        source = self.edit.toPlainText()
        name = os.path.basename(self._path)
        try:
            compile(source, self._path, "exec")
        except SyntaxError as exc:
            with open(self._path, "w", encoding="utf-8") as fh:
                fh.write(source)          # persist anyway, register nothing
            self.dirty = False
            line = exc.lineno or 1
            self._set_status(
                f"{name} saved — SYNTAX ERROR line {line}: {exc.msg}",
                ok=False)
            self.edit.go_to_line(line)
            return False
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write(source)
        self.dirty = False
        try:
            load_custom_module(self._path)
        except Exception as exc:
            self._set_status(f"{name} saved — load failed: "
                             f"{exc.__class__.__name__}: {exc}", ok=False)
            return False
        self._set_status(f"{name} saved and reloaded — available in the "
                         f"Add menus.", ok=True)
        return True

    def _set_status(self, message: str, ok: bool) -> None:
        color = ACCENTS["text-light"] if ok else ACCENTS["red"]
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(message)
        self.status_message.emit(message)
