# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Reflection-based field editors — the Python counterpart of 's
PropertyElement + SerializationUtils.CreateChildProperties.

``build_fields_widget(obj, ...)`` walks the public attributes of a
polymorphic item and creates matching editors:

- PropertyGet/PropertySet  -> label + source-dropdown button + nested sub-fields
- InstructionList/ConditionList/BranchList -> nested polymorphic list widget
- bool/int/float/str       -> checkbox / spinbox / line edit (or combo when the
                              class declares FIELD_CHOICES)
Variable-name fields offer existing graph/global variable names in an
editable combo box.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QSpinBox, QVBoxLayout, QWidget)

from polytess.core.conditions import BranchList, ConditionList
from polytess.core.instructions import InstructionList
from polytess.core.metadata import get_field_help, get_meta, humanize
from polytess.core.properties import PropertyGet, PropertySet
from polytess.gui.icons import icon
from polytess.gui.theme import INDENT
from polytess.gui.type_selector import TypeSelectorPopup
from polytess.gui.widgets import DropdownButton, VariableRefField

LABEL_WIDTH = 110
_SKIP_ATTRS = {"is_enabled", "breakpoint"}


def make_label(text: str, depth: int = 0, help_text: str = "",
               bold: bool = False) -> QLabel:
    """Field label; nesting indents the label only — editors stay
    aligned in one column. Block-parameter labels are bold and carry
    the FIELD_HELP tooltip (the tooltip lives on the parameter NAME,
    never on the value editor)."""
    label = QLabel(text)
    label.setFixedWidth(LABEL_WIDTH)
    label.setIndent(depth * INDENT)
    if bold:
        font = label.font()
        font.setBold(True)
        label.setFont(font)
    if help_text:
        label.setToolTip(help_text)
    return label


def _var_ref_provider(obj, attr: str, graph):
    """None if *attr* is not a variable/list/table reference; otherwise a
    callable returning the current (name, type_id) candidates for the picker.

    Sources declare what their ``name`` field references via the ``ref_kind``
    class attribute ("variable" | "list" | "table"); legacy scope+name pairs
    (e.g. GetListElement) are resolved through their ``scope`` field."""
    from polytess.core.variables import GlobalScope
    scope = getattr(obj, "scope", None)
    cls_name = type(obj).__name__
    ref_kind = getattr(type(obj), "ref_kind", None)

    if attr == "name" and ref_kind is not None:
        kind, is_global = ref_kind, "Global" in cls_name
    elif attr == "list_name":
        kind, is_global = "list", scope == "global"
    elif attr == "table_name":
        kind, is_global = "table", scope == "global"
    elif attr == "name":
        if not ("Global" in cls_name or "Graph" in cls_name
                or scope in ("graph", "global")):
            return None
        kind = "variable"
        is_global = "Global" in cls_name or ("Graph" not in cls_name
                                             and scope == "global")
    else:
        return None

    def items() -> list[tuple[str, str]]:
        if kind == "list":
            coll = GlobalScope.instance().lists if is_global \
                else (graph.lists if graph is not None else None)
            type_filter = None
        else:
            coll = GlobalScope.instance().variables if is_global \
                else (graph.variables if graph is not None else None)
            type_filter = "table" if kind == "table" else None
        if coll is None:
            return []
        return [(v.name, v.type_id) for v in coll
                if type_filter is None or v.type_id == type_filter]

    return items


class PropertyFieldRow(QWidget):
    """Label + source dropdown + indented sub-fields."""

    def __init__(self, label: str, prop, on_changed: Callable[[], None],
                 graph=None, depth: int = 0, parent=None, undo=None,
                 help_text: str = ""):
        super().__init__(parent)
        self._prop = prop
        self._on_changed = on_changed
        self._graph = graph
        self._depth = depth
        self._undo = undo
        self._help_text = help_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(make_label(label, depth, help_text=help_text,
                                 bold=True))

        self.button = DropdownButton()
        self.button.setLayoutDirection(Qt.LeftToRight)
        self.button.clicked.connect(self._open_selector)
        row.addWidget(self.button, 1)
        layout.addLayout(row)

        self.sub_container = QWidget()
        sub_layout = QVBoxLayout(self.sub_container)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(2)
        layout.addWidget(self.sub_container)

        self._rebuild()

    def _rebuild(self) -> None:
        source = self._prop.source
        m = get_meta(type(source))
        self.button.setText(m.title)
        self.button.setIcon(icon(m.icon, m.color))

        sub_layout = self.sub_container.layout()
        while sub_layout.count():
            child = sub_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        sub = build_fields_widget(source, self._on_changed, graph=self._graph,
                                  depth=self._depth + 1, undo=self._undo,
                                  inherited_help=self._help_text)
        if sub is not None:
            sub_layout.addWidget(sub)
        self.sub_container.setVisible(sub is not None)

    def _open_selector(self) -> None:
        candidates = type(self._prop).compatible_sources()
        kind = "set" if isinstance(self._prop, PropertySet) else "get"

        def pick(cls):
            old_source = self._prop.source
            self._prop.source = cls()
            self._rebuild()
            self._on_changed()
            if self._undo is not None:
                self._undo.push_field(self._prop, "source", old_source,
                                      self._prop.source, "Change Source")

        popup = TypeSelectorPopup(candidates, pick, parent=self.window(),
                                  favorites_key=f"sources-{kind}-{type(self._prop).value_type}")
        popup.open_at(self.button.mapToGlobal(self.button.rect().bottomLeft()))


def _scalar_editor(obj, attr: str, value, on_changed: Callable[[], None],
                   graph=None, undo=None) -> QWidget | None:
    choices = getattr(type(obj), "FIELD_CHOICES", {}).get(attr)

    def commit(v) -> None:
        old = getattr(obj, attr)
        if old == v:
            return
        setattr(obj, attr, v)
        on_changed()
        if undo is not None:
            undo.push_field(obj, attr, old, v, f"Edit {humanize(attr).title()}")

    if attr == "sign" and isinstance(value, bool):
        combo = QComboBox()
        combo.addItems(["If", "Not"])
        combo.setCurrentIndex(0 if value else 1)
        combo.currentIndexChanged.connect(lambda idx: commit(idx == 0))
        return combo
    if isinstance(value, bool):
        box = QCheckBox()
        box.setChecked(value)
        box.toggled.connect(commit)
        return box
    if isinstance(value, list):
        # direct list entry (GetConstantList.items)
        from polytess.gui.widgets import StringListEdit
        list_edit = StringListEdit(value)
        list_edit.changed.connect(commit)
        return list_edit
    if isinstance(value, int):
        spin = QSpinBox()
        spin.setRange(-10**9, 10**9)
        spin.setValue(value)
        spin.valueChanged.connect(lambda v: commit(int(v)))
        return spin
    if isinstance(value, float):
        spin = QDoubleSpinBox()
        spin.setRange(-1e12, 1e12)
        spin.setDecimals(6)
        spin.setValue(value)
        spin.valueChanged.connect(lambda v: commit(float(v)))
        return spin
    if isinstance(value, str):
        # constant path fields get a browse button (file/folder dialog)
        if attr == "value" and getattr(type(obj), "value_type", "") == "path":
            from polytess.gui.widgets import PathEdit
            path_edit = PathEdit(value)
            path_edit.textChanged.connect(commit)
            return path_edit
        # Formatted String/Path templates: variable-insert button + preview
        if attr == "template":
            from polytess.gui.widgets import TemplateEdit
            template_edit = TemplateEdit(value, graph)
            template_edit.textChanged.connect(commit)
            return template_edit
        if choices:
            combo = QComboBox()
            combo.addItems(list(choices))
            if value in choices:
                combo.setCurrentText(value)
            combo.currentTextChanged.connect(commit)
            return combo
        provider = _var_ref_provider(obj, attr, graph)
        if provider is not None:
            field = VariableRefField(value, provider)
            field.textChanged.connect(commit)
            return field
        edit = QLineEdit(value)
        edit.textChanged.connect(commit)
        return edit
    return None


def build_fields_widget(obj, on_changed: Callable[[], None], graph=None,
                        parent=None, depth: int = 0, undo=None,
                        inherited_help: str = "") -> QWidget | None:
    """Editor widget for all public fields of *obj*; None if it has none.

    *undo* is an ``UndoCallbacks`` (see inspector/commands.py) or None —
    threaded through to every nested field/list editor so edits become
    undoable; None falls back to applying changes directly (e.g. a
    widget built in isolation in a test).

    *inherited_help* is the owning parameter's FIELD_HELP when *obj* is
    a property source: its sub-rows (Variable / Value / Template …)
    then explain the actual parameter instead of the generic source
    mechanics."""
    from polytess.gui.inspector.poly_list import PolymorphicListWidget
    from polytess.core.instructions import Instruction
    from polytess.core.conditions import Branch, Condition
    from polytess.core.properties import PropertySource, SetSource

    entries = [(k, v) for k, v in vars(obj).items()
               if not k.startswith("_") and k not in _SKIP_ATTRS]
    if isinstance(getattr(obj, "sign", None), bool) and "sign" in vars(obj):
        pass   # sign handled like any attr (rendered as If/Not combo)
    if not entries:
        return None

    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(4)
    grid.setVerticalSpacing(3)
    grid_row = 0

    helps = get_field_help(type(obj))
    is_source = isinstance(obj, (PropertySource, SetSource))
    for attr, value in entries:
        label_text = humanize(attr).title()
        # Source sub-rows describe the owning parameter, not the source
        # mechanics; block parameters use their own FIELD_HELP and are
        # rendered bold (the tooltip sits on the parameter name).
        help_text = (inherited_help or helps.get(attr, "")) if is_source \
            else helps.get(attr, "")
        bold = not is_source
        if attr == "name" and getattr(type(obj), "ref_kind", None):
            label_text = "Variable"      # the reference row is labelled 'Variable'
        if isinstance(value, (PropertyGet, PropertySet)):
            layout.addLayout(grid) if grid_row else None
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(4)
            grid.setVerticalSpacing(3)
            grid_row = 0
            layout.addWidget(PropertyFieldRow(label_text, value, on_changed,
                                              graph, depth=depth, undo=undo,
                                              help_text=help_text))
        elif isinstance(value, InstructionList):
            lst = PolymorphicListWidget(label_text, Instruction, value.instructions,
                                        graph=graph, favorites_key="instructions",
                                        undo=undo)
            lst.changed.connect(on_changed)
            if help_text:
                lst.setToolTip(help_text)
            layout.addWidget(lst)
        elif isinstance(value, ConditionList):
            lst = PolymorphicListWidget(label_text, Condition, value.conditions,
                                        graph=graph, favorites_key="conditions",
                                        undo=undo)
            lst.changed.connect(on_changed)
            if help_text:
                lst.setToolTip(help_text)
            layout.addWidget(lst)
        elif isinstance(value, BranchList):
            lst = PolymorphicListWidget(label_text, Branch, value.branches,
                                        graph=graph, favorites_key="branches",
                                        direct_add_cls=Branch, undo=undo)
            lst.changed.connect(on_changed)
            if help_text:
                lst.setToolTip(help_text)
            layout.addWidget(lst)
        else:
            editor = _scalar_editor(obj, attr, value, on_changed, graph, undo)
            if editor is None:
                continue
            grid.addWidget(make_label(label_text, depth, help_text=help_text,
                                      bold=bold), grid_row, 0)
            grid.addWidget(editor, grid_row, 1)
            grid_row += 1

    if grid_row:
        layout.addLayout(grid)
    return widget
