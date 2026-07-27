# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Node inspector (right dock).

Shows the selected node: header (icon, editable name, enabled toggle),
the payload editor (the same Actions/Conditions/Branch/Event lists that the
node previews inline) and the reorderable "Transitions" list of outgoing
connections.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QToolButton, QVBoxLayout, QWidget)

from polytess.core.conditions import Branch, Condition
from polytess.core.events import Event
from polytess.core.instructions import Instruction
from polytess.core.metadata import get_meta, iter_subclasses
from polytess.graph.model import Graph, Node
from polytess.graph.nodes import (ActionsNode, BranchNode, ConditionsNode,
                                ExitNode, StartNode, SubGraphNode, TriggerNode)
from polytess.gui.icons import icon
from polytess.gui.inspector.fields import build_fields_widget, make_label
from polytess.gui.inspector.poly_list import PolymorphicListWidget
from polytess.gui.theme import ACCENTS, COLORS
from polytess.gui.type_selector import TypeSelectorPopup
from polytess.gui.widgets import DropdownButton


class InspectorPanel(QWidget):

    node_changed = Signal(object)      # node payload/name edited
    graph_changed = Signal()           # edges edited (transitions)
    open_subgraph = Signal(str)        # request to open a sub-workflow file

    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Node | None = None
        self._graph: Graph | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self.scroll)
        self._placeholder()

    # ---- public API ------------------------------------------------------- #

    def set_node(self, node: Node | None, graph: Graph | None) -> None:
        self._node = node
        self._graph = graph
        if node is None or graph is None:
            self._placeholder()
        else:
            self._build()

    def refresh_transitions(self) -> None:
        if self._node is not None:
            self._build()

    # ---- building ----------------------------------------------------------- #

    def _placeholder(self) -> None:
        label = QLabel("No node selected")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {ACCENTS['text-light']};")
        self.scroll.setWidget(label)

    def _emit_changed(self) -> None:
        if self._node is not None:
            self.node_changed.emit(self._node)

    def _build(self) -> None:   # noqa: C901
        node, graph = self._node, self._graph
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ---- header ------------------------------------------------------- #
        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg-dark']};"
            f" border: 1px solid {COLORS['border-default']}; border-radius: 3px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
            f"QCheckBox {{ border: none; background: transparent; }}")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(6, 4, 6, 4)
        icon_label = QLabel()
        icon_label.setPixmap(icon(node.icon, node.accent if node.accent in ACCENTS
                                  else "blue").pixmap(20, 20))
        head_layout.addWidget(icon_label)

        if node.renamable:
            name_edit = QLineEdit(node.custom_name)
            name_edit.setPlaceholderText(node.default_name)
            name_edit.textChanged.connect(
                lambda text: (setattr(node, "custom_name", text), self._emit_changed()))
            head_layout.addWidget(name_edit, 1)
        else:
            name_label = QLabel(f"<b>{node.name}</b>")
            head_layout.addWidget(name_label, 1)

        enabled_box = QCheckBox("Enabled")
        enabled_box.setChecked(node.enabled)
        enabled_box.toggled.connect(
            lambda value: (setattr(node, "enabled", value), self._emit_changed()))
        head_layout.addWidget(enabled_box)

        bp_box = QCheckBox("Breakpoint")
        bp_box.setChecked(node.breakpoint)
        bp_box.setToolTip("Pause execution when this node starts (shortcut: B)")
        bp_box.toggled.connect(
            lambda value: (setattr(node, "breakpoint", value), self._emit_changed()))
        head_layout.addWidget(bp_box)
        layout.addWidget(header)

        type_label = QLabel(f"{get_meta(type(node)).title} — "
                            f"{get_meta(type(node)).description}")
        type_label.setWordWrap(True)
        type_label.setStyleSheet(f"color: {ACCENTS['text-light']};")
        layout.addWidget(type_label)

        # ---- payload -------------------------------------------------------- #
        if isinstance(node, (StartNode, ExitNode, ActionsNode)):
            layout.addWidget(self._list_widget("Instructions", Instruction,
                                               node.instructions.instructions,
                                               "instructions"))
        elif isinstance(node, ConditionsNode):
            mode_row = QHBoxLayout()
            mode_row.addWidget(make_label("Check Mode"))
            mode_combo = QComboBox()
            mode_combo.addItems(["and", "or"])
            mode_combo.setCurrentText(node.check_mode)
            mode_combo.currentTextChanged.connect(
                lambda value: (setattr(node, "check_mode", value), self._emit_changed()))
            mode_row.addWidget(mode_combo, 1)
            layout.addLayout(mode_row)
            layout.addWidget(self._list_widget("Conditions", Condition,
                                               node.conditions.conditions,
                                               "conditions"))
        elif isinstance(node, BranchNode):
            layout.addWidget(self._list_widget("Branches", Branch,
                                               node.branches.branches,
                                               "branches", direct_add_cls=Branch))
        elif isinstance(node, TriggerNode):
            layout.addWidget(self._event_editor(node))
        elif isinstance(node, SubGraphNode):
            layout.addWidget(self._subgraph_editor(node))

        # ---- transitions ------------------------------------------------------ #
        transitions = self._transitions_widget(node, graph)
        if transitions is not None:
            layout.addWidget(transitions)

        layout.addStretch(1)
        self.scroll.setWidget(content)

    def _list_widget(self, title: str, base_cls, items: list, fav_key: str,
                     direct_add_cls=None) -> PolymorphicListWidget:
        widget = PolymorphicListWidget(title, base_cls, items, graph=self._graph,
                                       favorites_key=fav_key,
                                       direct_add_cls=direct_add_cls)
        widget.changed.connect(self._emit_changed)
        return widget

    # ---- trigger event editor ------------------------------------------------ #

    def _event_editor(self, node: TriggerNode) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        row = QHBoxLayout()
        row.addWidget(make_label("Event"))
        button = DropdownButton()
        if node.event is not None:
            m = get_meta(type(node.event))
            button.setText(m.title)
            button.setIcon(icon(m.icon, m.color))
        else:
            button.setText("(choose event…)")

        def pick(cls):
            node.event = cls()
            self._emit_changed()
            self._build()

        def open_popup():
            popup = TypeSelectorPopup(list(iter_subclasses(Event)), pick,
                                      parent=self.window(), favorites_key="events")
            popup.open_at(button.mapToGlobal(button.rect().bottomLeft()))

        button.clicked.connect(open_popup)
        row.addWidget(button, 1)
        layout.addLayout(row)

        if node.event is not None:
            fields = build_fields_widget(node.event, self._emit_changed,
                                         graph=self._graph, depth=1)
            if fields is not None:
                layout.addWidget(fields)
        return container

    # ---- sub-workflow editor --------------------------------------------------- #

    def _subgraph_editor(self, node: SubGraphNode) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        row = QHBoxLayout()
        row.addWidget(make_label("Workflow File"))
        edit = QLineEdit(node.file)
        edit.textChanged.connect(
            lambda text: (setattr(node, "file", text), self._emit_changed()))
        row.addWidget(edit, 1)
        browse = QToolButton()
        browse.setIcon(icon("folder", "text-light"))
        browse.setToolTip("Browse…")

        def do_browse():
            path, _ = QFileDialog.getOpenFileName(
                self, "Select workflow", "", "Workflows (*.flow.json)")
            if path:
                edit.setText(path)

        browse.clicked.connect(do_browse)
        row.addWidget(browse)
        layout.addLayout(row)

        open_btn = QPushButton("  Open Sub-Workflow")
        open_btn.setIcon(icon("graph", "blue"))
        open_btn.clicked.connect(lambda: self.open_subgraph.emit(node.file))
        layout.addWidget(open_btn)
        return container

    # ---- transitions ------------------------------------------------------------- #

    def _transitions_widget(self, node: Node, graph: Graph) -> QWidget | None:
        edges = graph.out_edges(node)
        if not node.ports("out"):
            return None
        container = QFrame()
        container.setStyleSheet(
            f"QFrame {{ background: {COLORS['bg-dark']};"
            f" border: 1px solid {COLORS['border-default']}; border-radius: 3px; }}"
            f"QLabel {{ border: none; background: transparent; }}"
            f"QToolButton {{ border: none; background: transparent; }}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(2)
        title = QLabel(f"<b>Transitions</b> ({len(edges)})")
        layout.addWidget(title)

        if not edges:
            hint = QLabel("No outgoing connections")
            hint.setStyleSheet(f"color: {ACCENTS['text-light']}; border: none;")
            layout.addWidget(hint)
            return container

        for position, edge in enumerate(edges):
            target = graph.node_by_guid(edge.dst_node)
            row = QHBoxLayout()
            row.setSpacing(3)
            port_spec = node.port(edge.src_port)
            port_label = port_spec.label if port_spec else edge.src_port
            text = QLabel(f"{port_label}  →  {target.name if target else '?'}")
            row.addWidget(text, 1)

            up = QToolButton(); up.setIcon(icon("chevron-up", "text-light"))
            up.setEnabled(position > 0)
            up.clicked.connect(lambda checked=False, e=edge: self._move_edge(e, -1))
            row.addWidget(up)
            down = QToolButton(); down.setIcon(icon("chevron-down", "text-light"))
            down.setEnabled(position < len(edges) - 1)
            down.clicked.connect(lambda checked=False, e=edge: self._move_edge(e, +1))
            row.addWidget(down)
            remove = QToolButton(); remove.setIcon(icon("minus", "text-light"))
            remove.setToolTip("Disconnect")
            remove.clicked.connect(lambda checked=False, e=edge: self._remove_edge(e))
            row.addWidget(remove)
            layout.addLayout(row)
        return container

    def _move_edge(self, edge, delta: int) -> None:
        graph = self._graph
        node = self._node
        siblings = graph.out_edges(node)
        index = siblings.index(edge)
        target_index = index + delta
        if not (0 <= target_index < len(siblings)):
            return
        other = siblings[target_index]
        i, j = graph.edges.index(edge), graph.edges.index(other)
        graph.edges[i], graph.edges[j] = graph.edges[j], graph.edges[i]
        self.graph_changed.emit()
        self._build()

    def _remove_edge(self, edge) -> None:
        self._graph.remove_edge(edge)
        self.graph_changed.emit()
        self._build()
