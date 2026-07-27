# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""References dialog — where is a variable read/written in the graph?
Double-clicking a row selects and centers the node in the editor."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from polytess.core.refs import Reference
from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS

_ACCESS_COLORS = {"read": ACCENTS["green"], "write": ACCENTS["red"],
                  "read/write": ACCENTS["yellow"]}
_ROLE_GUID = Qt.UserRole


class ReferencesDialog(QDialog):

    def __init__(self, name: str, scope: str, references: list[Reference],
                 on_goto: Callable[[str], None] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"References: {name}")
        self.setWindowIcon(icon("search", "text"))
        self.resize(760, 380)
        self.setModal(False)
        self._on_goto = on_goto

        layout = QVBoxLayout(self)
        reads = sum(1 for r in references if "read" in r.access)
        writes = sum(1 for r in references if "write" in r.access)
        summary = QLabel(
            f"<b>{name}</b> ({scope}) — {len(references)} reference(s): "
            f"<span style='color:{_ACCESS_COLORS['read']}'>{reads} read</span>, "
            f"<span style='color:{_ACCESS_COLORS['write']}'>{writes} write</span>"
            + ("" if references else "<br><i>not referenced in this graph</i>"))
        layout.addWidget(summary)

        self.table = QTableWidget(len(references), 4)
        self.table.setHorizontalHeaderLabels(["Node", "Location", "Access", "Detail"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self._goto)

        for row, ref in enumerate(references):
            node_item = QTableWidgetItem(ref.node_name)
            node_item.setData(_ROLE_GUID, ref.node_guid)
            location = ref.location
            if len(location) > 70:
                location = location[:67] + "…"
            access_item = QTableWidgetItem(ref.access)
            access_item.setForeground(QColor(_ACCESS_COLORS.get(ref.access,
                                                                ACCENTS["text"])))
            detail = ref.detail + (f"  [{ref.scope}]" if ref.scope != "?" else "")
            for column, item in enumerate((node_item, QTableWidgetItem(location),
                                           access_item, QTableWidgetItem(detail))):
                self.table.setItem(row, column, item)
        layout.addWidget(self.table, 1)

        hint = QLabel("Double-click a row to select the node in the graph.")
        hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        layout.addWidget(hint)

    def _goto(self, item: QTableWidgetItem) -> None:
        guid_item = self.table.item(item.row(), 0)
        if guid_item is not None and self._on_goto is not None:
            self._on_goto(guid_item.data(_ROLE_GUID))
