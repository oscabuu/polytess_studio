# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Blackboard (left dock) — pinned blackboard: graph variables,
graph lists and global variables with live values during a run.

- Name variables: scalar slots (bool / number / integer / string / path)
  with a colored type icon, sortable by name/type (header click),
  searchable, and filterable by type. Path values get a browse button.
- List variables: expandable inline lists — click a list open to see
  its elements, edit them inline (double click), add/remove rows with +/−.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                               QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMenu,
                               QTabWidget, QTableWidget, QTableWidgetItem,
                               QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from polytess.core.metadata import get_meta
from polytess.core.values import create_value, value_types
from polytess.core.variables import GlobalScope, ListVariables, NameVariables
from polytess.gui.icons import icon
from polytess.gui.widgets import VARIABLE_MIME, PathEdit

# "null" is internal, plain lists live in the Lists section — keep the
# scalar type choice unambiguous (user feedback).
SCALAR_TYPES = [t for t in value_types() if t not in ("null", "list")]


def type_icon(type_id: str):
    """Colored icon for a value type (from the Value class @meta)."""
    cls = value_types().get(type_id)
    if cls is None:
        return icon("variable", "text-light")
    m = get_meta(cls)
    return icon(m.icon, m.color)


def _variable_mime(name: str) -> QMimeData:
    data = QMimeData()
    data.setText(name)
    data.setData(VARIABLE_MIME, name.encode("utf-8"))
    return data


class _DragTable(QTableWidget):
    """Variable rows drag their name into inspector reference fields
    (pull a variable from the blackboard into a slot). Dropping a
    variable row back onto the table moves it into the group of the
    target row (``on_drop_to_group`` callback set by the owner)."""

    def __init__(self, rows: int, columns: int, parent=None):
        super().__init__(rows, columns, parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.on_drop_to_group = None      # callable(name, group) | None
        self.group_of_row = None          # callable(row) -> str | None
        from PySide6.QtCore import QSize
        from polytess.gui.theme import ICON_SIZE, ROW_HEIGHT
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT + 2)

    def mimeData(self, items):
        for item in items:
            name = self.item(item.row(), 0)
            if name is not None and name.data(Qt.UserRole):
                return _variable_mime(name.data(Qt.UserRole))
        return super().mimeData(items)

    def dragEnterEvent(self, event):     # noqa: N802 (Qt API)
        if self.on_drop_to_group is not None \
                and event.mimeData().hasFormat(VARIABLE_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):      # noqa: N802 (Qt API)
        if self.on_drop_to_group is not None \
                and event.mimeData().hasFormat(VARIABLE_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):          # noqa: N802 (Qt API)
        if self.on_drop_to_group is None \
                or not event.mimeData().hasFormat(VARIABLE_MIME):
            super().dropEvent(event)
            return
        name = bytes(event.mimeData().data(VARIABLE_MIME)).decode("utf-8")
        row = self.rowAt(int(event.position().y()))
        group = self.group_of_row(row) if self.group_of_row else None
        if group is not None:
            self.on_drop_to_group(name, group)
            event.acceptProposedAction()


class _DragTree(QTreeWidget):
    """List rows (and their elements) drag the list name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        from PySide6.QtCore import QSize
        from polytess.gui.theme import ICON_SIZE
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))

    def mimeData(self, items):
        for item in items:
            top = item if item.parent() is None else item.parent()
            name = top.data(0, Qt.UserRole)
            if name:
                return _variable_mime(name)
        return super().mimeData(items)


class _NewVariableDialog(QDialog):

    def __init__(self, parent=None, title: str = "New Variable",
                 with_value: bool = True):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        layout.addRow("Name", self.name_edit)
        self.type_combo = QComboBox()
        for type_id in SCALAR_TYPES:
            self.type_combo.addItem(type_icon(type_id), type_id)
        self.type_combo.setCurrentText("string")
        layout.addRow("Type", self.type_combo)
        self.value_edit = QLineEdit()
        if with_value:
            layout.addRow("Value", self.value_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.name_edit.setFocus()


class _FilterHeader(QHBoxLayout):
    """Shared header row: title · search field · type filter · extra buttons."""

    def __init__(self, title: str, on_search, on_filter_types, buttons):
        super().__init__()
        self.addWidget(QLabel(f"<b>{title}</b>"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(on_search)
        self.addWidget(self.search, 1)

        self.filter_button = QToolButton()
        self.filter_button.setIcon(icon("filter", "text-light"))
        self.filter_button.setToolTip("Filter by type")
        self.filter_button.setAutoRaise(True)
        self._filter_types: set[str] = set()
        self._on_filter_types = on_filter_types
        self.filter_button.clicked.connect(self._open_filter_menu)
        self.addWidget(self.filter_button)

        for btn in buttons:
            self.addWidget(btn)

    @property
    def filter_types(self) -> set[str]:
        return self._filter_types

    def _open_filter_menu(self) -> None:
        menu = QMenu(self.filter_button)
        all_action = menu.addAction("All types")
        all_action.setEnabled(bool(self._filter_types))
        menu.addSeparator()
        actions = {}
        for type_id in SCALAR_TYPES:
            action = menu.addAction(type_icon(type_id), type_id)
            action.setCheckable(True)
            action.setChecked(type_id in self._filter_types)
            actions[action] = type_id
        chosen = menu.exec(self.filter_button.mapToGlobal(
            self.filter_button.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen is all_action:
            self._filter_types = set()
        else:
            type_id = actions[chosen]
            if type_id in self._filter_types:
                self._filter_types.discard(type_id)
            else:
                self._filter_types.add(type_id)
        active = bool(self._filter_types)
        self.filter_button.setIcon(icon("filter", "blue" if active else "text-light"))
        self._on_filter_types()


class _VariablesTable(QWidget):
    """Name/type/value table bound to a NameVariables collection.

    Variables can be organized into named groups (collapsible header
    rows). Group membership is pure metadata on the variable — moving a
    variable never touches references. Renames rewrite all references
    in the current graph (``rename_references``), so they don't break
    nodes either."""

    changed = Signal()
    find_refs = Signal(str)     # variable name

    _GROUP_ROLE = Qt.UserRole + 1     # group name on a group-header row

    def __init__(self, parent=None, scope: str = "graph",
                 graph_provider=None):
        super().__init__(parent)
        self.variables: NameVariables | None = None
        self._scope = scope
        self._graph_provider = graph_provider
        self._collapsed: set[str] = set()
        self._updating = False
        self._sort_column: int | None = None
        self._sort_asc = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        add_btn = QToolButton(); add_btn.setIcon(icon("plus", "text-light"))
        add_btn.setToolTip("Add variable")
        add_btn.clicked.connect(self._add)
        remove_btn = QToolButton(); remove_btn.setIcon(icon("minus", "text-light"))
        remove_btn.setToolTip("Remove selected variable")
        remove_btn.clicked.connect(self._remove)
        self.header_bar = _FilterHeader("Variables", lambda _t: self.refresh(),
                                        self.refresh, (add_btn, remove_btn))
        layout.addLayout(self.header_bar)

        self.table = _DragTable(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort_by)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.on_drop_to_group = self._set_group
        self.table.group_of_row = self._group_of_row
        layout.addWidget(self.table, 1)

    def _context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        header_item = self.table.item(row, 0) if row >= 0 else None
        group = header_item.data(self._GROUP_ROLE) \
            if header_item is not None else None
        if group is not None:
            menu = QMenu(self)
            menu.addAction(icon("edit", "text-light"), "Rename Group…",
                           lambda: self._rename_group(group))
            menu.addAction(icon("trash", "text-light"), "Delete Group",
                           lambda: self._delete_group(group))
            menu.exec(self.table.viewport().mapToGlobal(pos))
            return
        name = self._row_name(row) if row >= 0 else None
        if not name:
            return
        menu = QMenu(self)
        menu.addAction(icon("search", "text-light"), f"Find References of '{name}'…",
                       lambda: self.find_refs.emit(name))
        group_menu = menu.addMenu(icon("folder", "text-light"),
                                  "Move to Group")
        var = self.variables.variable(name) if self.variables else None
        current = var.group if var is not None else ""
        no_group = group_menu.addAction("(no group)")
        no_group.setEnabled(current != "")
        no_group.triggered.connect(
            lambda checked=False, n=name: self._set_group(n, ""))
        existing = self._group_names()
        if existing:
            group_menu.addSeparator()
        for group in existing:
            action = group_menu.addAction(group)
            action.setEnabled(group != current)
            action.triggered.connect(
                lambda checked=False, n=name, g=group: self._set_group(n, g))
        group_menu.addSeparator()
        group_menu.addAction("New group…",
                             lambda n=name: self._move_to_new_group(n))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ---- groups ---------------------------------------------------------------- #

    def _group_names(self) -> list[str]:
        if self.variables is None:
            return []
        seen: dict[str, None] = {}
        for var in self.variables:
            if getattr(var, "group", ""):
                seen[var.group] = None
        return sorted(seen)

    def _group_of_row(self, row: int) -> str | None:
        """Group a drop on *row* targets: the header row's own group, a
        member row's group ('' for ungrouped rows); None = no valid row."""
        if row < 0:
            return ""                    # empty area below -> ungrouped
        item = self.table.item(row, 0)
        if item is None:
            return None
        header_group = item.data(self._GROUP_ROLE)
        if header_group is not None:
            return header_group
        name = item.data(Qt.UserRole)
        if name and self.variables is not None:
            var = self.variables.variable(name)
            return getattr(var, "group", "") if var is not None else None
        return None

    def _set_group(self, name: str, group: str) -> None:
        if self.variables is None:
            return
        var = self.variables.variable(name)
        if var is None or getattr(var, "group", "") == group:
            return
        var.group = group
        self._collapsed.discard(group)   # show where it landed
        self.refresh()
        self.changed.emit()

    def _move_to_new_group(self, name: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        group, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if ok and group.strip():
            self._set_group(name, group.strip())

    def _members_of(self, group: str) -> list:
        if self.variables is None:
            return []
        return [v for v in self.variables
                if getattr(v, "group", "") == group]

    def _rename_group(self, group: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Group",
                                            "Group name:", text=group)
        new_name = new_name.strip()
        if ok and new_name and new_name != group:
            self._apply_group_rename(group, new_name)

    def _apply_group_rename(self, group: str, new_name: str) -> None:
        for var in self._members_of(group):
            var.group = new_name
        if group in self._collapsed:
            self._collapsed.discard(group)
            self._collapsed.add(new_name)
        self.refresh()
        self.changed.emit()

    def _delete_group(self, group: str) -> None:
        """Dissolve the group: every member moves out (variables are
        never deleted with the group)."""
        for var in self._members_of(group):
            var.group = ""
        self._collapsed.discard(group)
        self.refresh()
        self.changed.emit()

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        group = item.data(self._GROUP_ROLE) if item is not None else None
        if group is None:
            return
        if group in self._collapsed:
            self._collapsed.discard(group)
        else:
            self._collapsed.add(group)
        self.refresh()

    # ---- binding -------------------------------------------------------------- #

    def set_collection(self, variables: NameVariables | None) -> None:
        if self.variables is not None and self._on_external in self.variables.on_change:
            self.variables.on_change.remove(self._on_external)
        self.variables = variables
        if variables is not None:
            variables.on_change.append(self._on_external)
        self.refresh()

    def _on_external(self, _name: str) -> None:
        if not self._updating:
            self.refresh()

    # ---- sorting / filtering ---------------------------------------------------- #

    def _sort_by(self, column: int) -> None:
        if column > 1:
            return
        if self._sort_column == column:
            if self._sort_asc:
                self._sort_asc = False
            else:                       # third click: back to insertion order
                self._sort_column = None
                self._sort_asc = True
        else:
            self._sort_column, self._sort_asc = column, True
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(self._sort_column is not None)
        if self._sort_column is not None:
            header.setSortIndicator(self._sort_column,
                                    Qt.AscendingOrder if self._sort_asc
                                    else Qt.DescendingOrder)
        self.refresh()

    def _visible_variables(self):
        if self.variables is None:
            return []
        text = self.header_bar.search.text().strip().lower()
        types = self.header_bar.filter_types
        out = []
        for var in self.variables:
            if types and var.type_id not in types:
                continue
            if text and text not in var.name.lower() \
                    and text not in str(var.value.get()).lower():
                continue
            out.append(var)
        if self._sort_column == 0:
            out.sort(key=lambda v: v.name.lower(), reverse=not self._sort_asc)
        elif self._sort_column == 1:
            out.sort(key=lambda v: (v.type_id, v.name.lower()),
                     reverse=not self._sort_asc)
        return out

    # ---- populate ------------------------------------------------------------------ #

    def refresh(self) -> None:
        self._updating = True
        self.table.setRowCount(0)
        visible = self._visible_variables()
        ungrouped = [v for v in visible if not getattr(v, "group", "")]
        grouped: dict[str, list] = {}
        for var in visible:
            group = getattr(var, "group", "")
            if group:
                grouped.setdefault(group, []).append(var)
        for var in ungrouped:
            self._append_variable_row(var)
        for group in sorted(grouped):
            self._append_group_header(group, len(grouped[group]))
            if group not in self._collapsed:
                for var in grouped[group]:
                    self._append_variable_row(var)
        self._updating = False

    def _append_group_header(self, group: str, count: int) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        arrow = "▸" if group in self._collapsed else "▾"
        header = QTableWidgetItem(f"{arrow} {group}  ({count})")
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        header.setFlags((header.flags() | Qt.ItemIsEnabled)
                        & ~Qt.ItemIsEditable & ~Qt.ItemIsDragEnabled)
        header.setData(self._GROUP_ROLE, group)
        self.table.setItem(row, 0, header)
        self.table.setSpan(row, 0, 1, 3)

    def _append_variable_row(self, var) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(var.name)
        name_item.setIcon(type_icon(var.type_id))
        name_item.setData(Qt.UserRole, var.name)
        self.table.setItem(row, 0, name_item)
        type_item = QTableWidgetItem(var.type_id)
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, type_item)
        if var.type_id == "path":
            placeholder = QTableWidgetItem("")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, placeholder)
            editor = PathEdit(str(var.value.get()))
            editor.textChanged.connect(
                lambda text, name=var.name: self._set_value(name, text))
            self.table.setCellWidget(row, 2, editor)
        elif var.type_id == "table":
            from polytess.gui.widgets import TableSummaryEdit
            placeholder = QTableWidgetItem("")
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, placeholder)
            editor = TableSummaryEdit(var.value.get(),
                                      f"Table: {var.name}")
            editor.changed.connect(
                lambda table, name=var.name: self._set_value(name, table))
            self.table.setCellWidget(row, 2, editor)
        elif var.type_id == "vector3":
            from polytess.core.values import format_vector3
            self.table.setItem(
                row, 2, QTableWidgetItem(format_vector3(var.value.get())))
        elif var.type_id == "transform":
            from polytess.core.values import format_vector3
            value = var.value.get()
            self.table.setItem(row, 2, QTableWidgetItem(
                f"{format_vector3(value['pos'])} | "
                f"{format_vector3(value['rot'])}"))
        else:
            self.table.setItem(row, 2, QTableWidgetItem(str(var.value.get())))

    def _row_name(self, row: int) -> str | None:
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _set_value(self, name: str, text: str) -> None:
        if self._updating or self.variables is None:
            return
        var = self.variables.variable(name)
        if var is None:
            return
        self._updating = True
        try:
            try:
                var.value.set(text)
            except (TypeError, ValueError):
                pass
            self.variables._emit(name)
        finally:
            self._updating = False
        self.changed.emit()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or self.variables is None:
            return
        row, column = item.row(), item.column()
        name = self._row_name(row)
        if name is None:
            return
        if column == 0:
            new_name = item.text().strip()
            self._updating = True
            self.variables.rename(name, new_name)
            self._updating = False
            if new_name and new_name != name \
                    and self.variables.exists(new_name):
                self._rename_references(name, new_name)
            self.refresh()
            self.changed.emit()
        elif column == 2:
            self._set_value(name, item.text())
            self.refresh()

    def _rename_references(self, old: str, new: str) -> None:
        """Rewrite references in the current graph so the rename does not
        break any node (sources, plain name fields, {old} templates)."""
        graph = self._graph_provider() if self._graph_provider else None
        if graph is None:
            return
        from polytess.core.refs import rename_references
        count = rename_references(graph, old, new, self._scope)
        if count:
            self.changed.emit()

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """Table variables open the spreadsheet editor on the value cell."""
        if column != 2 or self.variables is None:
            return
        name = self._row_name(row)
        var = self.variables.variable(name) if name else None
        if var is None or var.type_id != "table":
            return
        from polytess.gui.widgets import TableEditorDialog
        from PySide6.QtWidgets import QDialog as _QDialog
        dialog = TableEditorDialog(var.value.get(), f"Table: {name}", self)
        if dialog.exec() == _QDialog.Accepted:
            self._set_value(name, dialog.result_table())
            self.refresh()

    def _add(self) -> None:
        if self.variables is None:
            return
        dialog = _NewVariableDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        name = dialog.name_edit.text().strip()
        if not name or self.variables.exists(name):
            return
        self.variables.declare(name, dialog.type_combo.currentText(),
                               dialog.value_edit.text() or None)
        self.refresh()
        self.changed.emit()

    def _remove(self) -> None:
        if self.variables is None:
            return
        name = self._row_name(self.table.currentRow())
        if name is not None:
            self.variables.remove(name)
            self.refresh()
            self.changed.emit()


class _ListsPanel(QWidget):
    """Expandable lists: top level = list variables,
    children = editable elements; + / − add and remove rows."""

    changed = Signal()
    find_refs = Signal(str)     # list name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lists: ListVariables | None = None
        self._updating = False
        self._sort_column: int | None = None
        self._sort_asc = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        add_list_btn = QToolButton(); add_list_btn.setIcon(icon("list", "text-light"))
        add_list_btn.setToolTip("Add list")
        add_list_btn.clicked.connect(self._add_list)
        add_btn = QToolButton(); add_btn.setIcon(icon("plus", "text-light"))
        add_btn.setToolTip("Add element to selected list")
        add_btn.clicked.connect(self._add_element)
        remove_btn = QToolButton(); remove_btn.setIcon(icon("minus", "text-light"))
        remove_btn.setToolTip("Remove selected element / list")
        remove_btn.clicked.connect(self._remove_selected)
        self.header_bar = _FilterHeader("Lists", lambda _t: self.refresh(),
                                        self.refresh,
                                        (add_list_btn, add_btn, remove_btn))
        layout.addLayout(self.header_bar)

        self.tree = _DragTree()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Name", "Value"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionsClickable(True)
        self.tree.header().sectionClicked.connect(self._sort_by)
        self.tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.tree.itemDoubleClicked.connect(self._edit_item)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.setRootIsDecorated(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        top = item if item.parent() is None else item.parent()
        name = top.data(0, Qt.UserRole)
        if not name:
            return
        menu = QMenu(self)
        menu.addAction(icon("search", "text-light"), f"Find References of '{name}'…",
                       lambda: self.find_refs.emit(name))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ---- binding ----------------------------------------------------------- #

    def set_collection(self, lists: ListVariables | None) -> None:
        if self.lists is not None and self._on_external in self.lists.on_change:
            self.lists.on_change.remove(self._on_external)
        self.lists = lists
        if lists is not None:
            lists.on_change.append(self._on_external)
        self.refresh()

    def _on_external(self, _name: str) -> None:
        if not self._updating:
            self.refresh()

    # ---- sorting / filtering ------------------------------------------------- #

    def _sort_by(self, column: int) -> None:
        if self._sort_column == column:
            if self._sort_asc:
                self._sort_asc = False
            else:
                self._sort_column = None
                self._sort_asc = True
        else:
            self._sort_column, self._sort_asc = column, True
        header = self.tree.header()
        header.setSortIndicatorShown(self._sort_column is not None)
        if self._sort_column is not None:
            header.setSortIndicator(self._sort_column,
                                    Qt.AscendingOrder if self._sort_asc
                                    else Qt.DescendingOrder)
        self.refresh()

    def _visible_lists(self):
        if self.lists is None:
            return []
        text = self.header_bar.search.text().strip().lower()
        types = self.header_bar.filter_types
        out = []
        for lst in self.lists:
            if types and lst.type_id not in types:
                continue
            if text and text not in lst.name.lower() \
                    and not any(text in str(v).lower() for v in lst.items):
                continue
            out.append(lst)
        if self._sort_column == 0:
            out.sort(key=lambda l: l.name.lower(), reverse=not self._sort_asc)
        elif self._sort_column == 1:
            out.sort(key=lambda l: (l.type_id, l.name.lower()),
                     reverse=not self._sort_asc)
        return out

    # ---- populate --------------------------------------------------------------- #

    def refresh(self) -> None:
        self._updating = True
        expanded = {self.tree.topLevelItem(i).data(0, Qt.UserRole)
                    for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        self.tree.clear()
        for lst in self._visible_lists():
            top = QTreeWidgetItem([lst.name, f"{lst.type_id}  [{len(lst)}]"])
            top.setData(0, Qt.UserRole, lst.name)
            top.setIcon(0, type_icon(lst.type_id))
            top.setForeground(1, Qt.gray)
            top.setFlags(top.flags() | Qt.ItemIsEditable)
            self.tree.addTopLevelItem(top)
            for index, value in enumerate(lst.items):
                if lst.type_id == "path":
                    # path elements get a browse button instead of inline text
                    child = QTreeWidgetItem([str(index), ""])
                    child.setForeground(0, Qt.gray)
                    top.addChild(child)
                    editor = PathEdit(str(value))
                    editor.textChanged.connect(
                        lambda text, name=lst.name, i=index:
                        self._set_element(name, i, text))
                    self.tree.setItemWidget(child, 1, editor)
                else:
                    child = QTreeWidgetItem([str(index), str(value)])
                    child.setForeground(0, Qt.gray)
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                    top.addChild(child)
            top.setExpanded(lst.name in expanded)
        self._updating = False

    # ---- selection helpers ---------------------------------------------------- #

    def _selected(self) -> tuple[str | None, int | None]:
        """(list name, element index | None) of the current selection."""
        item = self.tree.currentItem()
        if item is None:
            return None, None
        parent = item.parent()
        if parent is None:
            return item.data(0, Qt.UserRole), None
        return parent.data(0, Qt.UserRole), parent.indexOfChild(item)

    # ---- editing ------------------------------------------------------------------ #

    def _set_element(self, name: str, index: int, text: str) -> None:
        """Value edit from a PathEdit widget (no refresh while typing)."""
        if self._updating or self.lists is None:
            return
        lst = self.lists.get(name)
        if lst is None or not (0 <= index < len(lst)):
            return
        self._updating = True
        try:
            lst.set(index, text)
            self.lists.notify(name)
        finally:
            self._updating = False
        self.changed.emit()

    def _edit_item(self, item: QTreeWidgetItem, column: int) -> None:
        if item.parent() is None and column == 0:      # rename list
            self.tree.editItem(item, 0)
        elif item.parent() is not None and column == 1:  # edit element value
            if self.tree.itemWidget(item, 1) is None:   # path rows use PathEdit
                self.tree.editItem(item, 1)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating or self.lists is None:
            return
        parent = item.parent()
        if parent is None and column == 0:
            old = item.data(0, Qt.UserRole)
            new = item.text(0).strip()
            if new and new != old:
                self._updating = True
                self.lists.rename(old, new)
                self._updating = False
            self.refresh()
            self.changed.emit()
        elif parent is not None and column == 1:
            name = parent.data(0, Qt.UserRole)
            lst = self.lists.get(name)
            index = parent.indexOfChild(item)
            if lst is not None and 0 <= index < len(lst):
                try:
                    lst.set(index, item.text(1))
                except (TypeError, ValueError):
                    pass
                self._updating = True
                self.lists.notify(name)
                self._updating = False
                self.refresh()
                self.changed.emit()

    def _add_list(self) -> None:
        if self.lists is None:
            return
        dialog = _NewVariableDialog(self, "New List", with_value=False)
        if dialog.exec() != QDialog.Accepted:
            return
        name = dialog.name_edit.text().strip()
        if not name or self.lists.exists(name):
            return
        self.lists.declare(name, dialog.type_combo.currentText())
        self.refresh()
        self._expand(name)
        self.changed.emit()

    def _add_element(self) -> None:
        if self.lists is None:
            return
        name, _index = self._selected()
        if name is None:
            if len(self.lists) == 1:
                name = self.lists.names()[0]
            else:
                return
        lst = self.lists.get(name)
        if lst is None:
            return
        lst.push(create_value(lst.type_id).get())
        self._updating = True
        self.lists.notify(name)
        self._updating = False
        self.refresh()
        self._expand(name)
        self.changed.emit()

    def _remove_selected(self) -> None:
        if self.lists is None:
            return
        name, index = self._selected()
        if name is None:
            return
        if index is None:
            self.lists.remove(name)
        else:
            lst = self.lists.get(name)
            if lst is not None and 0 <= index < len(lst):
                lst.remove_at(index)
                self._updating = True
                self.lists.notify(name)
                self._updating = False
        self.refresh()
        if index is not None:
            self._expand(name)
        self.changed.emit()

    def _expand(self, name: str) -> None:
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.data(0, Qt.UserRole) == name:
                top.setExpanded(True)
                return


class BlackboardPanel(QWidget):

    changed = Signal()
    find_references = Signal(str, str)   # (name, scope: "graph" | "global")

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        self._graph = None
        self.graph_vars = _VariablesTable(
            scope="graph", graph_provider=lambda: self._graph)
        self.graph_lists = _ListsPanel()
        graph_page = QWidget()
        graph_layout = QVBoxLayout(graph_page)
        graph_layout.setContentsMargins(2, 2, 2, 2)
        graph_layout.addWidget(self.graph_vars, 3)
        graph_layout.addWidget(self.graph_lists, 2)
        tabs.addTab(graph_page, "Graph")

        self.global_vars = _VariablesTable(
            scope="global", graph_provider=lambda: self._graph)
        self.global_lists = _ListsPanel()
        global_page = QWidget()
        global_layout = QVBoxLayout(global_page)
        global_layout.setContentsMargins(2, 2, 2, 2)
        global_layout.addWidget(self.global_vars, 3)
        global_layout.addWidget(self.global_lists, 2)
        tabs.addTab(global_page, "Global")

        scope = GlobalScope.instance()
        self.global_vars.set_collection(scope.variables)
        self.global_lists.set_collection(scope.lists)

        for widget in (self.graph_vars, self.graph_lists,
                       self.global_vars, self.global_lists):
            widget.changed.connect(self.changed)
        for widget, scope in ((self.graph_vars, "graph"),
                              (self.graph_lists, "graph"),
                              (self.global_vars, "global"),
                              (self.global_lists, "global")):
            widget.find_refs.connect(
                lambda name, s=scope: self.find_references.emit(name, s))

    def set_graph(self, graph) -> None:
        self._graph = graph
        self.graph_vars.set_collection(graph.variables if graph else None)
        self.graph_lists.set_collection(graph.lists if graph else None)
