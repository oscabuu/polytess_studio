# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Example gallery — File → New from Example… opens curated flows as
unsaved copies (the originals stay untouched)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS

_ASSETS_EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "assets", "examples")


def example_flows() -> list[tuple[str, str, str]]:
    """(group, display name, path) — bundled tutorials first, then every
    flow found under <install>/examples/**."""
    out: list[tuple[str, str, str]] = []

    def add_dir(folder: str, group: str) -> None:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return
        for name in names:
            full = os.path.join(folder, name)
            if os.path.isdir(full):
                add_dir(full, os.path.basename(full))
            elif name.endswith(".flow.json"):
                display = name.replace(".flow.json", "").replace("_", " ")
                out.append((group, display, full))

    add_dir(_ASSETS_EXAMPLES, "Tutorials")
    from polytess.core.userdir import install_roots
    for root in install_roots():
        add_dir(os.path.join(root, "examples"), "Examples")
    seen: set[str] = set()
    unique = []
    for group, display, path in out:
        key = os.path.basename(path)
        if key not in seen:
            seen.add(key)
            unique.append((group, display, path))
    return unique


class ExampleGalleryDialog(QDialog):
    """Grouped list of example flows; double-click (or Open) picks one."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New from Example")
        self.resize(520, 460)
        self.selected_path: str = ""

        layout = QVBoxLayout(self)
        hint = QLabel("Examples open as unsaved copies — experiment "
                      "freely, the originals stay untouched.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {ACCENTS['text-light']};")
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        groups: dict[str, QTreeWidgetItem] = {}
        for group, display, path in example_flows():
            if group not in groups:
                groups[group] = QTreeWidgetItem([group])
                groups[group].setIcon(0, icon("folder", "text-light"))
                self.tree.addTopLevelItem(groups[group])
                groups[group].setExpanded(True)
            item = QTreeWidgetItem([display])
            item.setIcon(0, icon("graph", "teal"))
            item.setData(0, Qt.UserRole, path)
            groups[group].addChild(item)
        self.tree.itemDoubleClicked.connect(lambda *_: self._accept())
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Open |
                                   QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        item = self.tree.currentItem()
        path = item.data(0, Qt.UserRole) if item else None
        if path:
            self.selected_path = path
            self.accept()
