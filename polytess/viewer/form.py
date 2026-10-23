# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""The input form — built from an ``InputSpec`` (polytess.graph.inputs).

One widget per field, chosen by type and metadata: line edit, spin box,
True/False combo, choices combo, path edit with browse button, date
edit, editable list. Sections = variable groups. ``values()`` returns
``{name: value}``; ``validate()`` marks invalid fields and returns the
problems; ``set_values()`` fills from a preset."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QScrollArea, QSpinBox, QToolButton,
                               QVBoxLayout, QWidget)

from polytess.graph.inputs import InputField, InputSpec, validate_values
from polytess.gui.icons import icon


class _ListEditor(QWidget):
    """Editable list of plain values (one per row, + / −)."""

    changed = Signal()

    def __init__(self, items: list, path_like: bool = False, parent=None):
        super().__init__(parent)
        self._path_like = path_like
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.list = QListWidget()
        self.list.setMaximumHeight(120)
        self.list.itemChanged.connect(lambda _i: self.changed.emit())
        layout.addWidget(self.list)
        bar = QHBoxLayout()
        add = QToolButton(); add.setIcon(icon("plus", "text-light"))
        add.setToolTip("Add entry")
        add.clicked.connect(self._add)
        remove = QToolButton(); remove.setIcon(icon("minus", "text-light"))
        remove.setToolTip("Remove selected entry")
        remove.clicked.connect(self._remove)
        bar.addWidget(add); bar.addWidget(remove)
        if path_like:
            browse = QToolButton(); browse.setIcon(icon("folder", "text-light"))
            browse.setToolTip("Add files…")
            browse.clicked.connect(self._browse)
            bar.addWidget(browse)
        bar.addStretch(1)
        layout.addLayout(bar)
        self.set_items(items)

    def _row(self, value) -> None:
        item = QListWidgetItem(str(value))
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.list.addItem(item)

    def set_items(self, items: list) -> None:
        self.list.clear()
        for value in items or []:
            self._row(value)

    def items(self) -> list:
        return [self.list.item(i).text() for i in range(self.list.count())]

    def _add(self) -> None:
        self._row("")
        self.list.editItem(self.list.item(self.list.count() - 1))
        self.changed.emit()

    def _remove(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.changed.emit()

    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add files")
        for path in paths:
            self._row(path)
        if paths:
            self.changed.emit()


class _PathField(QWidget):
    """Line edit + browse button honouring path_kind (file / folder)."""

    changed = Signal()

    def __init__(self, field: InputField, parent=None):
        super().__init__(parent)
        self._field = field
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.edit = QLineEdit(str(field.value or ""))
        self.edit.setPlaceholderText("folder" if field.path_kind == "folder"
                                     else "file" if field.path_kind == "file"
                                     else "path")
        self.edit.textChanged.connect(lambda _t: self.changed.emit())
        layout.addWidget(self.edit, 1)
        browse = QToolButton(); browse.setIcon(icon("folder", "text-light"))
        browse.setToolTip("Browse…")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)

    def _browse(self) -> None:
        start = self.edit.text() or os.path.expanduser("~")
        if self._field.path_kind == "folder":
            path = QFileDialog.getExistingDirectory(self, self._field.label, start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._field.label, start)
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, value) -> None:
        self.edit.setText("" if value is None else str(value))


class InputForm(QScrollArea):
    """Scrollable form for an InputSpec."""

    changed = Signal()

    def __init__(self, spec: InputSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._editors: dict[str, tuple[InputField, QWidget]] = {}
        self._errors: dict[str, QLabel] = {}
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 12, 4)
        layout.setSpacing(6)
        if not spec.fields:
            empty = QLabel("This flow needs no input — just start it.")
            empty.setObjectName("hint")
            layout.addWidget(empty)
        for section in spec.sections:
            if section.title:
                head = QLabel(section.title)
                head.setObjectName("section")
                layout.addWidget(head)
            form = QFormLayout()
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
            form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            form.setHorizontalSpacing(14)
            for field in section.fields:
                self._add_field(form, field)
            layout.addLayout(form)
        layout.addStretch(1)

    # ---- building ------------------------------------------------------------- #

    def _add_field(self, form: QFormLayout, field: InputField) -> None:
        editor = self._editor_for(field)
        label_text = field.label + (" *" if field.required else "")
        label = QLabel(label_text)
        if field.required:
            label.setToolTip("Required")
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(1)
        box.addWidget(editor)
        if field.description:
            hint = QLabel(field.description)
            hint.setObjectName("hint")
            hint.setToolTip(field.description)
            box.addWidget(hint)
        error = QLabel("")
        error.setObjectName("error")
        error.hide()
        box.addWidget(error)
        holder = QWidget()
        holder.setLayout(box)
        form.addRow(label, holder)
        self._editors[field.name] = (field, editor)
        self._errors[field.name] = error

    def _editor_for(self, field: InputField) -> QWidget:
        if field.kind == "list":
            editor = _ListEditor(list(field.value or []),
                                 path_like=field.type_id == "path")
            editor.changed.connect(self.changed)
            return editor
        if field.choices:
            combo = QComboBox()
            for choice in field.choices:
                combo.addItem(str(choice), choice)
            index = combo.findData(field.value)
            if index < 0:
                index = combo.findText(str(field.value))
            combo.setCurrentIndex(max(index, 0))
            combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
            return combo
        if field.type_id == "bool":
            combo = QComboBox()
            combo.addItem("True", True)
            combo.addItem("False", False)
            combo.setCurrentIndex(0 if field.value else 1)
            combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
            return combo
        if field.type_id == "integer":
            spin = QSpinBox()
            spin.setMinimumWidth(160)
            spin.setRange(int(field.minimum) if field.minimum is not None else -10**9,
                          int(field.maximum) if field.maximum is not None else 10**9)
            spin.setValue(int(field.value or 0))
            spin.valueChanged.connect(lambda _v: self.changed.emit())
            return spin
        if field.type_id == "number":
            spin = QDoubleSpinBox()
            spin.setMinimumWidth(160)
            spin.setDecimals(4)
            spin.setRange(field.minimum if field.minimum is not None else -1e12,
                          field.maximum if field.maximum is not None else 1e12)
            spin.setValue(float(field.value or 0))
            spin.valueChanged.connect(lambda _v: self.changed.emit())
            return spin
        if field.type_id == "path":
            editor = _PathField(field)
            editor.changed.connect(self.changed)
            return editor
        edit = QLineEdit("" if field.value is None else str(field.value))
        if field.type_id == "date":
            edit.setPlaceholderText("YYYY-MM-DD [HH:MM]")
        edit.textChanged.connect(lambda _t: self.changed.emit())
        return edit

    # ---- values -------------------------------------------------------------------- #

    def value_of(self, name: str):
        field, editor = self._editors[name]
        if isinstance(editor, _ListEditor):
            return editor.items()
        if isinstance(editor, QComboBox):
            return editor.currentData()
        if isinstance(editor, (QSpinBox, QDoubleSpinBox)):
            return editor.value()
        if isinstance(editor, _PathField):
            return editor.value()
        return editor.text()

    def values(self) -> dict:
        return {name: self.value_of(name) for name in self._editors}

    def set_values(self, values: dict) -> list[str]:
        """Fill editors from *values*; returns names the form doesn't have."""
        unknown = []
        for name, value in values.items():
            if name not in self._editors:
                unknown.append(name)
                continue
            field, editor = self._editors[name]
            if isinstance(editor, _ListEditor):
                editor.set_items(list(value or []))
            elif isinstance(editor, QComboBox):
                index = editor.findData(value)
                if index < 0:
                    index = editor.findText(str(value))
                if index >= 0:
                    editor.setCurrentIndex(index)
            elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
                try:
                    editor.setValue(type(editor.value())(value))
                except (TypeError, ValueError):
                    pass
            elif isinstance(editor, _PathField):
                editor.set_value(value)
            else:
                editor.setText("" if value is None else str(value))
        return unknown

    def reset_defaults(self) -> None:
        self.set_values({f.name: f.value for f in self.spec.fields})

    # ---- validation ----------------------------------------------------------------- #

    def validate(self) -> list[str]:
        problems = validate_values(self.spec, self.values())
        by_label: dict[str, str] = {}
        for problem in problems:
            label, _, text = problem.partition(": ")
            by_label.setdefault(label, text)
        for name, (field, editor) in self._editors.items():
            message = by_label.get(field.label, "")
            error = self._errors[name]
            error.setText(message)
            error.setVisible(bool(message))
            target = editor.edit if isinstance(editor, _PathField) else editor
            target.setProperty("invalid", bool(message))
            target.style().unpolish(target)
            target.style().polish(target)
        return problems

    def set_enabled(self, enabled: bool) -> None:
        for _field, editor in self._editors.values():
            editor.setEnabled(enabled)
