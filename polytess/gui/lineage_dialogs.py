# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Flow lifecycle dialogs — structural diff view and history browser."""

from __future__ import annotations

import datetime
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout)

from polytess.graph.lineage import FlowDiff
from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS


class FlowDiffDialog(QDialog):
    """Grouped list of everything that differs between two flow states.

    ``jump_callback(guid)`` — when given, clicking an entry jumps to the
    node on the canvas (the dialog is meant to be shown non-modally)."""

    def __init__(self, diff: FlowDiff, base_tag: str, other_tag: str,
                 parent=None, jump_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Compare flows")
        self.resize(560, 460)
        self._jump = jump_callback
        layout = QVBoxLayout(self)

        header = QLabel(f"<b>{other_tag}</b> compared with <b>{base_tag}</b>"
                        f" — {diff.summary()}")
        header.setWordWrap(True)
        layout.addWidget(header)

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        groups = (
            ("Nodes added", "plus", "green", diff.nodes_added),
            ("Nodes removed", "minus", "red", diff.nodes_removed),
            ("Nodes changed", "edit", "yellow", diff.nodes_changed),
            ("Connections added", "arrow-right", "green", diff.edges_added),
            ("Connections removed", "arrow-right", "red", diff.edges_removed),
            ("Variables changed", "variable", "yellow", diff.variables_changed),
        )
        for title, icon_name, color, items in groups:
            if not items:
                continue
            top = QTreeWidgetItem([f"{title} ({len(items)})"])
            top.setIcon(0, icon(icon_name, color))
            tree.addTopLevelItem(top)
            for entry in items:
                child = QTreeWidgetItem([entry])
                guid = getattr(entry, "guid", "")
                if guid and jump_callback is not None:
                    child.setData(0, Qt.UserRole, guid)
                    child.setToolTip(0, "Click to jump to this node")
                top.addChild(child)
            top.setExpanded(True)
        if diff.is_empty:
            empty = QTreeWidgetItem(["No differences — the flows are identical."])
            tree.addTopLevelItem(empty)
        tree.itemClicked.connect(self._on_clicked)
        layout.addWidget(tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _on_clicked(self, item, _column) -> None:
        guid = item.data(0, Qt.UserRole)
        if guid and self._jump is not None:
            self._jump(guid)


class FlowHistoryDialog(QDialog):
    """Snapshots of one flow family, newest first; double-click opens."""

    def __init__(self, snapshots: list[str], open_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flow history")
        self.resize(520, 420)
        self._open = open_callback
        layout = QVBoxLayout(self)

        hint = QLabel("Every studio save files a snapshot — double-click to "
                      "open one (read it or branch from it; the current flow "
                      "stays untouched).")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Revision", "Saved"])
        self.tree.setRootIsDecorated(False)
        for path in snapshots:
            name = os.path.basename(path)
            stamp = datetime.datetime.fromtimestamp(
                os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            item = QTreeWidgetItem([name.replace(".flow.json", ""), stamp])
            item.setData(0, Qt.UserRole, path)
            item.setIcon(0, icon("graph", "teal"))
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)
        self.tree.itemDoubleClicked.connect(self._on_open)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_open(self, item, _column) -> None:
        path = item.data(0, Qt.UserRole)
        if path:
            self._open(path)
            self.accept()
