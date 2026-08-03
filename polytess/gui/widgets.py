# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Small reusable widgets."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QMenu, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS

# Mime type for variable names dragged from the blackboard into
# inspector reference fields (object drag & drop).
VARIABLE_MIME = "application/x-polytess-variable"


class DropdownButton(QPushButton):
    """Popup-style button: lighter selection field,
    left-aligned label and a ▼ arrow — visually distinct from inputs."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QPushButton { text-align: left; padding-left: 6px;"
            " padding-right: 20px; }")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ACCENTS["text-light"]))
        cx = self.rect().right() - 11
        cy = self.rect().center().y()
        painter.drawPolygon(QPolygonF([QPointF(cx - 4, cy - 2),
                                       QPointF(cx + 4, cy - 2),
                                       QPointF(cx, cy + 3)]))


class _VariableDropEdit(QLineEdit):
    """Line edit that swallows dropped variable names (replaces the text
    instead of inserting at the cursor)."""

    def dragEnterEvent(self, event) -> None:
        data = event.mimeData()
        if data.hasFormat(VARIABLE_MIME) or data.hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        data = event.mimeData()
        if data.hasFormat(VARIABLE_MIME) or data.hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        data = event.mimeData()
        if data.hasFormat(VARIABLE_MIME):
            name = bytes(data.data(VARIABLE_MIME)).decode("utf-8")
        elif data.hasText():
            name = data.text()
        else:
            super().dropEvent(event)
            return
        self.setText(name.strip())
        event.acceptProposedAction()


class VariableRefField(QWidget):
    """Object/reference field: dark input (free text stays
    possible) plus a ⊙ picker inside the field listing all candidates;
    variables can also be dragged in from the blackboard."""

    textChanged = Signal(str)

    def __init__(self, text: str = "",
                 items_provider: Callable[[], list[tuple[str, str]]] | None = None,
                 parent=None):
        # items_provider returns the current (name, type_id) candidates —
        # evaluated lazily so freshly created variables show up.
        super().__init__(parent)
        self._items_provider = items_provider
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.edit = _VariableDropEdit(text)
        self.edit.setPlaceholderText("(variable name)")
        self.edit.textChanged.connect(self.textChanged)
        layout.addWidget(self.edit, 1)
        action = self.edit.addAction(icon("target", "text-light"),
                                     QLineEdit.TrailingPosition)
        action.setToolTip("Pick variable…")
        action.triggered.connect(self._open_picker)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    def _open_picker(self) -> None:
        from polytess.gui.blackboard import type_icon
        items = self._items_provider() if self._items_provider else []
        menu = QMenu(self)
        if not items:
            empty = menu.addAction("(no variables declared)")
            empty.setEnabled(False)
        for name, type_id in items:
            action = menu.addAction(type_icon(type_id), name)
            action.triggered.connect(
                lambda checked=False, n=name: self.edit.setText(n))
        menu.exec(self.mapToGlobal(self.rect().bottomRight()
                                   - QPointF(menu.sizeHint().width(), 0).toPoint()))


class StringListEdit(QWidget):
    """Inline editor for a direct list entry (GetConstantList.items):
    one line edit per element plus +/− buttons — compact inline list."""

    changed = Signal(list)

    def __init__(self, items: list | None = None, parent=None):
        super().__init__(parent)
        self._items = [str(v) for v in (items or [])]
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._rebuild()

    def _rebuild(self) -> None:
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for index, value in enumerate(self._items):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)
            edit = QLineEdit(value)
            edit.textChanged.connect(
                lambda text, i=index: self._set_item(i, text))
            row_layout.addWidget(edit, 1)
            remove = QToolButton()
            remove.setIcon(icon("minus", "text-light"))
            remove.setToolTip("Remove element")
            remove.setAutoRaise(True)
            remove.clicked.connect(lambda checked=False, i=index: self._remove(i))
            row_layout.addWidget(remove)
            self._layout.addWidget(row)
        add = QToolButton()
        add.setIcon(icon("plus", "text-light"))
        add.setToolTip("Add element")
        add.setAutoRaise(True)
        add.clicked.connect(self._add)
        self._layout.addWidget(add)

    def values(self) -> list[str]:
        return list(self._items)

    def _emit(self) -> None:
        self.changed.emit(list(self._items))

    def _set_item(self, index: int, text: str) -> None:
        if 0 <= index < len(self._items):
            self._items[index] = text
            self._emit()

    def _add(self) -> None:
        self._items.append("")
        self._rebuild()
        self._emit()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self._items):
            del self._items[index]
            self._rebuild()
            self._emit()


class PathEdit(QWidget):
    """Line edit for a path plus a browse button offering
    'Choose file…' / 'Choose folder…' — free text stays possible."""

    textChanged = Signal(str)

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.edit = QLineEdit(text)
        self.edit.textChanged.connect(self.textChanged)
        layout.addWidget(self.edit, 1)
        button = QToolButton()
        button.setIcon(icon("folder", "text-light"))
        button.setToolTip("Browse…")
        button.setAutoRaise(True)
        button.clicked.connect(self._browse)
        layout.addWidget(button)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    def _browse(self) -> None:
        menu = QMenu(self)
        menu.addAction("Choose file…", self._pick_file)
        menu.addAction("Choose folder…", self._pick_folder)
        menu.exec(self.mapToGlobal(self.rect().bottomRight()))

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file", self.edit.text())
        if path:
            self.edit.setText(path)

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", self.edit.text())
        if path:
            self.edit.setText(path)


class InlineTableEdit(QWidget):
    """Compact inline spreadsheet for a table variable
    ({"columns": [...], "rows": [...]}): headers on top, one grid row per
    table row, cells editable in place; +/− buttons manage rows and
    columns, the expand button opens the full TableEditorDialog."""

    changed = Signal(dict)

    MAX_HEIGHT = 168

    def __init__(self, table: dict, title: str = "Table", parent=None):
        super().__init__(parent)
        from polytess.core import tables as _tables
        from PySide6.QtWidgets import (QAbstractScrollArea, QTableWidget,
                                       QTableWidgetItem)
        self._tables = _tables
        self._QTableWidgetItem = QTableWidgetItem
        self._title = title
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(1)

        self.grid = QTableWidget()
        self.grid.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.grid.verticalHeader().setVisible(False)
        self.grid.verticalHeader().setDefaultSectionSize(20)
        self.grid.horizontalHeader().setDefaultSectionSize(84)
        self.grid.setMaximumHeight(self.MAX_HEIGHT)
        self.grid.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self.grid)

        bar = QHBoxLayout()
        bar.setSpacing(1)
        for icon_name, tip, slot in (
                ("plus", "Add row", self._add_row),
                ("minus", "Remove selected row", self._remove_row),
                ("list", "Add column…", self._add_column),
                ("cancel", "Remove selected column", self._remove_column),
                ("edit", "Open in the table editor…", self._open_dialog)):
            button = QToolButton()
            button.setIcon(icon(icon_name, "text-light"))
            button.setToolTip(tip)
            button.setAutoRaise(True)
            button.clicked.connect(slot)
            bar.addWidget(button)
        bar.addStretch(1)
        layout.addLayout(bar)

        self._load(table)

    # ---- data ------------------------------------------------------------- #

    def _load(self, table: dict) -> None:
        self._updating = True
        columns = self._tables.columns_of(table)
        rows = self._tables.rows_of(table)
        self.grid.setColumnCount(len(columns))
        self.grid.setHorizontalHeaderLabels(columns)
        self.grid.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, column in enumerate(columns):
                self.grid.setItem(r, c, self._QTableWidgetItem(
                    str(row.get(column, ""))))
        self._updating = False

    def table(self) -> dict:
        columns = [self.grid.horizontalHeaderItem(c).text()
                   for c in range(self.grid.columnCount())]
        rows = []
        for r in range(self.grid.rowCount()):
            row = {}
            for c, column in enumerate(columns):
                item = self.grid.item(r, c)
                row[column] = self._tables.convert_scalar(item.text()) \
                    if item is not None else ""
            rows.append(row)
        return {"columns": columns, "rows": rows}

    def preferred_height(self) -> int:
        header = self.grid.horizontalHeader().height()
        body = self.grid.rowCount() * self.grid.verticalHeader() \
            .defaultSectionSize()
        return min(self.MAX_HEIGHT, header + body + 8) + 26   # + button bar

    def _emit(self) -> None:
        if not self._updating:
            self.changed.emit(self.table())

    # ---- edits -------------------------------------------------------------- #

    def _on_cell_changed(self, _item) -> None:
        self._emit()

    def _add_row(self) -> None:
        self.grid.insertRow(self.grid.rowCount())
        self._emit()

    def _remove_row(self) -> None:
        row = self.grid.currentRow()
        if row >= 0:
            self.grid.removeRow(row)
            self._emit()

    def _add_column(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Column", "Name:")
        if ok and name.strip():
            index = self.grid.columnCount()
            self._updating = True
            self.grid.insertColumn(index)
            self.grid.setHorizontalHeaderItem(
                index, self._QTableWidgetItem(name.strip()))
            self._updating = False
            self._emit()

    def _remove_column(self) -> None:
        column = self.grid.currentColumn()
        if column >= 0:
            self.grid.removeColumn(column)
            self._emit()

    def _open_dialog(self) -> None:
        dialog = TableEditorDialog(self.table(), self._title, self)
        if dialog.exec() == QDialog.Accepted:
            self._load(dialog.result_table())
            self._emit()


class TableEditorDialog(QDialog):
    """Spreadsheet-style editor for a table variable
    ({"columns": [...], "rows": [...]})."""

    def __init__(self, table: dict, title: str = "Table", parent=None):
        super().__init__(parent)
        from polytess.core import tables as _tables
        self.setWindowTitle(title)
        self.resize(640, 420)
        self._tables = _tables

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        for text, slot in (("+ Row", self._add_row), ("− Row", self._remove_row),
                           ("+ Column", self._add_column),
                           ("− Column", self._remove_column)):
            button = QToolButton()
            button.setText(text)
            button.clicked.connect(slot)
            bar.addWidget(button)
        bar.addStretch(1)
        layout.addLayout(bar)

        from PySide6.QtWidgets import (QDialogButtonBox, QInputDialog,
                                       QTableWidget, QTableWidgetItem)
        self._QInputDialog = QInputDialog
        self._QTableWidgetItem = QTableWidgetItem
        self.grid = QTableWidget()
        layout.addWidget(self.grid, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load(table)

    def _load(self, table: dict) -> None:
        columns = self._tables.columns_of(table)
        rows = self._tables.rows_of(table)
        self.grid.setColumnCount(len(columns))
        self.grid.setHorizontalHeaderLabels(columns)
        self.grid.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, column in enumerate(columns):
                value = row.get(column, "")
                self.grid.setItem(r, c, self._QTableWidgetItem(str(value)))

    def result_table(self) -> dict:
        columns = [self.grid.horizontalHeaderItem(c).text()
                   for c in range(self.grid.columnCount())]
        rows = []
        for r in range(self.grid.rowCount()):
            row = {}
            for c, column in enumerate(columns):
                item = self.grid.item(r, c)
                row[column] = self._tables.convert_scalar(item.text()) \
                    if item is not None else ""
            rows.append(row)
        return {"columns": columns, "rows": rows}

    def _add_row(self) -> None:
        self.grid.insertRow(self.grid.rowCount())

    def _remove_row(self) -> None:
        row = self.grid.currentRow()
        if row >= 0:
            self.grid.removeRow(row)

    def _add_column(self) -> None:
        name, ok = self._QInputDialog.getText(self, "New Column", "Name:")
        if ok and name.strip():
            index = self.grid.columnCount()
            self.grid.insertColumn(index)
            self.grid.setHorizontalHeaderItem(
                index, self._QTableWidgetItem(name.strip()))

    def _remove_column(self) -> None:
        column = self.grid.currentColumn()
        if column >= 0:
            self.grid.removeColumn(column)


class TemplateEdit(QWidget):
    """Editor for Formatted String / Formatted Path templates:
    a '{x}' button lists all graph/global variables (plus {target} and
    {workdir}) and inserts the placeholder at the cursor; a live preview
    below shows the resolved result."""

    textChanged = Signal(str)

    def __init__(self, text: str = "", graph=None, parent=None):
        super().__init__(parent)
        self._graph = graph

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        row = QHBoxLayout()
        row.setSpacing(2)
        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText("e.g. out/{case}/result")
        self.edit.textChanged.connect(self._on_text_changed)
        row.addWidget(self.edit, 1)
        button = QToolButton()
        button.setIcon(icon("variable", "purple"))
        button.setToolTip("Insert variable placeholder…")
        button.setAutoRaise(True)
        button.clicked.connect(self._open_menu)
        row.addWidget(button)
        layout.addLayout(row)

        self.preview = QLabel("")
        self.preview.setStyleSheet(
            f"color: {ACCENTS['text-light']}; font-style: italic;"
            f" border: none; background: transparent;")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        self._update_preview()

    # ---- API -------------------------------------------------------------- #

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str) -> None:
        self.edit.setText(text)

    # ---- internals --------------------------------------------------------- #

    def _on_text_changed(self, text: str) -> None:
        self._update_preview()
        self.textChanged.emit(text)

    def insert_placeholder(self, name: str) -> None:
        self.edit.insert("{" + name + "}")
        self.edit.setFocus()

    def _open_menu(self) -> None:
        from polytess.core.variables import GlobalScope
        from polytess.gui.blackboard import type_icon
        menu = QMenu(self)
        if self._graph is not None and len(self._graph.variables):
            menu.addSection("Graph Variables")
            for var in self._graph.variables:
                action = menu.addAction(type_icon(var.type_id), var.name)
                action.triggered.connect(
                    lambda checked=False, n=var.name: self.insert_placeholder(n))
        global_vars = GlobalScope.instance().variables
        if len(global_vars):
            menu.addSection("Global Variables")
            for var in global_vars:
                action = menu.addAction(type_icon(var.type_id), var.name)
                action.triggered.connect(
                    lambda checked=False, n=var.name: self.insert_placeholder(n))
        menu.addSection("Special")
        for name, tip in (("target", "current element of Loop List / Loop Range"),
                          ("workdir", "workflow working directory")):
            action = menu.addAction(icon("target" if name == "target" else "folder",
                                         "teal"), name)
            action.setToolTip(tip)
            action.triggered.connect(
                lambda checked=False, n=name: self.insert_placeholder(n))
        menu.exec(self.mapToGlobal(self.rect().bottomRight()))

    def _update_preview(self) -> None:
        text = self.edit.text()
        if not text or "{" not in text:
            self.preview.setVisible(False)
            return
        try:
            from polytess.core.context import Context
            from polytess.core.properties import format_with_variables
            ctx = Context(graph=self._graph, logger=lambda l, m: None)
            resolved = format_with_variables(text, ctx)
        except Exception:
            resolved = text
        self.preview.setText(f"→  {resolved}")
        self.preview.setVisible(True)
