# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""GraphScene — the interactive canvas:
grid background, node/edge items, port-drag connection with rubber edge,
selection -> inspector, clipboard copy/paste, undo integration and
live status highlighting."""

from __future__ import annotations

import json

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPen, QUndoStack
from PySide6.QtWidgets import QGraphicsScene

from polytess.core.serialization import from_data, to_data
from polytess.graph.model import Graph, Group, Node, StickyNote, new_guid
from polytess.gui.graph.commands import (AddDecorationCommand, AddNodeCommand,
                                       ConnectCommand, MoveNodesCommand,
                                       PasteCommand, RemoveSelectionCommand)
from polytess.gui.graph.decorations import GroupItem, StickyNoteItem
from polytess.gui.graph.edge_item import EdgeItem, PendingEdgeItem
from polytess.gui.graph.node_item import NodeItem
from polytess.gui.theme import COLORS

GRID_MINOR = 20
GRID_MAJOR = 100
_CLIP_KEY = "$polytess-graph-clip"


class GraphScene(QGraphicsScene):

    selection_node_changed = Signal(object)     # Node | None
    modified = Signal()
    request_open_subgraph = Signal(str)

    def __init__(self, graph: Graph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.undo_stack = QUndoStack(self)
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: dict[str, EdgeItem] = {}
        self.deco_items: list = []
        self._statuses: dict[str, str] = {}
        self._pending: tuple[NodeItem, object] | None = None
        self._pending_item: PendingEdgeItem | None = None
        self._move_snapshot: list = []

        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.selectionChanged.connect(self._on_selection)
        self.sync_items()

    # ---- background grid ----------------------------------------------------- #

    def drawBackground(self, painter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(COLORS["canvas"]))
        for step, color in ((GRID_MINOR, COLORS["grid-minor"]),
                            (GRID_MAJOR, COLORS["grid-major"])):
            pen = QPen(QColor(color), 1)
            painter.setPen(pen)
            lines = []
            x = int(rect.left()) - (int(rect.left()) % step)
            while x < rect.right():
                lines.append(QLineF(x, rect.top(), x, rect.bottom()))
                x += step
            y = int(rect.top()) - (int(rect.top()) % step)
            while y < rect.bottom():
                lines.append(QLineF(rect.left(), y, rect.right(), y))
                y += step
            painter.drawLines(lines)

    # ---- item sync -------------------------------------------------------------- #

    def sync_items(self) -> None:
        """Rebuild items from the model, preserving selection and statuses."""
        selected = {item.node.guid for item in self.selected_nodes()}
        self.blockSignals(True)
        self.clear()
        self.node_items = {}
        self.edge_items = {}
        self.deco_items = []
        for group in self.graph.groups:
            item = GroupItem(self, group)
            self.addItem(item)
            self.deco_items.append(item)
        for note in self.graph.notes:
            item = StickyNoteItem(self, note)
            self.addItem(item)
            self.deco_items.append(item)
        for node in self.graph.nodes:
            item = NodeItem(self, node)
            self.addItem(item)
            self.node_items[node.guid] = item
            item.set_status(self._statuses.get(node.guid, "idle"))
            if node.guid in selected:
                item.setSelected(True)
        for edge in self.graph.edges:
            item = EdgeItem(self, edge)
            self.addItem(item)
            self.edge_items[edge.guid] = item
        self.blockSignals(False)
        self._on_selection()
        self.modified.emit()

    def sync_positions(self) -> None:
        for guid, item in self.node_items.items():
            node = self.graph.node_by_guid(guid)
            if node is not None:
                item.setPos(node.x, node.y)
        self.update_all_edges()
        self.modified.emit()

    def update_edges_for(self, guid: str) -> None:
        for item in self.edge_items.values():
            if guid in (item.edge.src_node, item.edge.dst_node):
                item.update_path()

    def update_all_edges(self) -> None:
        for item in self.edge_items.values():
            item.update_path()

    def update_node(self, node: Node) -> None:
        item = self.node_items.get(node.guid)
        if item is not None:
            item.sync_from_model()
            self.update_edges_for(node.guid)

    def mark_modified(self) -> None:
        self.modified.emit()

    # ---- status highlighting ------------------------------------------------------ #

    def set_status(self, node: Node, status: str) -> None:
        self._statuses[node.guid] = status
        item = self.node_items.get(node.guid)
        if item is not None:
            item.set_status(status)

    def clear_statuses(self) -> None:
        self._statuses.clear()
        for item in self.node_items.values():
            item.set_status("idle")

    # ---- selection ------------------------------------------------------------------ #

    def selected_nodes(self) -> list[NodeItem]:
        return [i for i in self.selectedItems() if isinstance(i, NodeItem)]

    def selected_edges(self) -> list[EdgeItem]:
        return [i for i in self.selectedItems() if isinstance(i, EdgeItem)]

    def _on_selection(self) -> None:
        nodes = self.selected_nodes()
        self.selection_node_changed.emit(nodes[0].node if len(nodes) == 1 else None)

    # ---- structure operations --------------------------------------------------------- #

    def add_node_at(self, node_cls: type, scene_pos: QPointF) -> None:
        node = node_cls()
        node.x, node.y = scene_pos.x(), scene_pos.y()
        self.undo_stack.push(AddNodeCommand(self, node))

    def delete_selection(self) -> None:
        nodes = [i.node for i in self.selected_nodes()]
        edges = [i.edge for i in self.selected_edges()]
        groups = [i.model for i in self.selectedItems() if isinstance(i, GroupItem)]
        notes = [i.model for i in self.selectedItems() if isinstance(i, StickyNoteItem)]
        if nodes or edges or groups or notes:
            self.undo_stack.push(
                RemoveSelectionCommand(self, nodes, edges, groups, notes))

    def add_group_at(self, scene_pos: QPointF) -> None:
        """Frame the current node selection; otherwise an
        empty default-sized group at the cursor."""
        selected = self.selected_nodes()
        if selected:
            rect = None
            for item in selected:
                item_rect = QRectF(item.pos().x(), item.pos().y(),
                                   item.width, item.height)
                rect = item_rect if rect is None else rect.united(item_rect)
            rect.adjust(-30, -30 - GroupItem.TITLE_H, 30, 30)
            group = Group("Group", rect.x(), rect.y(), rect.width(), rect.height())
        else:
            group = Group("Group", scene_pos.x(), scene_pos.y())
        self.undo_stack.push(AddDecorationCommand(self, group, "groups"))

    def add_note_at(self, scene_pos: QPointF) -> None:
        note = StickyNote("Note", "", scene_pos.x(), scene_pos.y())
        self.undo_stack.push(AddDecorationCommand(self, note, "notes"))

    # ---- clipboard ---------------------------------------------------------------------- #

    def copy_selection(self) -> None:
        from PySide6.QtWidgets import QApplication
        nodes = [i.node for i in self.selected_nodes() if i.node.deletable]
        if not nodes:
            return
        guids = {n.guid for n in nodes}
        edges = [e for e in self.graph.edges
                 if e.src_node in guids and e.dst_node in guids]
        payload = {_CLIP_KEY: True,
                   "nodes": [to_data(n) for n in nodes],
                   "edges": [to_data(e) for e in edges]}
        QApplication.clipboard().setText(json.dumps(payload))

    def paste(self, scene_pos: QPointF | None = None) -> None:
        from PySide6.QtWidgets import QApplication
        try:
            payload = json.loads(QApplication.clipboard().text())
        except Exception:
            return
        if not isinstance(payload, dict) or not payload.get(_CLIP_KEY):
            return
        text = json.dumps(payload)
        for node_data in payload.get("nodes", []):
            old = node_data.get("guid", "")
            if old:
                text = text.replace(old, new_guid())
        payload = json.loads(text)
        nodes = [from_data(d) for d in payload.get("nodes", [])]
        edges = [from_data(d) for d in payload.get("edges", [])]
        for edge in edges:
            edge.guid = new_guid()
        if not nodes:
            return
        min_x = min(n.x for n in nodes)
        min_y = min(n.y for n in nodes)
        if scene_pos is None:
            offset = QPointF(30, 30)
        else:
            offset = scene_pos - QPointF(min_x, min_y)
        for node in nodes:
            node.x += offset.x()
            node.y += offset.y()
        command = PasteCommand(self, nodes, edges)
        self.undo_stack.push(command)
        for node in nodes:
            item = self.node_items.get(node.guid)
            if item is not None:
                item.setSelected(True)

    def duplicate_selection(self) -> None:
        self.copy_selection()
        self.paste(None)

    def toggle_breakpoints(self) -> None:
        """Toggle the breakpoint flag on all selected nodes."""
        items = self.selected_nodes()
        if not items:
            return
        target = not all(item.node.breakpoint for item in items)
        for item in items:
            item.node.breakpoint = target
            item.update()
        self.modified.emit()

    # ---- mouse: port dragging ------------------------------------------------------------ #

    def _port_under(self, scene_pos: QPointF):
        for item in self.items(scene_pos):
            if isinstance(item, NodeItem):
                spec = item.port_at(item.mapFromScene(scene_pos))
                if spec is not None:
                    return item, spec
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hit = self._port_under(event.scenePos())
            if hit is not None:
                self._pending = hit
                self._pending_item = PendingEdgeItem()
                self.addItem(self._pending_item)
                src_item, spec = hit
                src = src_item.mapToScene(src_item.port_pos(spec))
                self._pending_item.update_points(src, event.scenePos(), spec.vertical)
                event.accept()
                return
            # snapshot for move-undo
            self._move_snapshot = [(i.node, (i.node.x, i.node.y))
                                   for i in self.selected_nodes()]
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton and not self._move_snapshot:
            self._move_snapshot = [(i.node, (i.node.x, i.node.y))
                                   for i in self.selected_nodes()]

    def mouseMoveEvent(self, event):
        if self._pending is not None and self._pending_item is not None:
            src_item, spec = self._pending
            src = src_item.mapToScene(src_item.port_pos(spec))
            self._pending_item.update_points(src, event.scenePos(), spec.vertical)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pending is not None:
            src_item, src_spec = self._pending
            self._pending = None
            if self._pending_item is not None:
                self.removeItem(self._pending_item)
                self._pending_item = None
            hit = self._port_under(event.scenePos())
            if hit is not None:
                dst_item, dst_spec = hit
                pair = None
                if src_spec.direction == "out" and dst_spec.direction == "in":
                    pair = (src_item.node, src_spec.name, dst_item.node, dst_spec.name)
                elif src_spec.direction == "in" and dst_spec.direction == "out":
                    pair = (dst_item.node, dst_spec.name, src_item.node, src_spec.name)
                if pair is not None and pair[0].guid != pair[2].guid:
                    self.undo_stack.push(ConnectCommand(self, *pair))
            event.accept()
            return

        super().mouseReleaseEvent(event)
        # move-undo bookkeeping
        if self._move_snapshot:
            changed = []
            for node, old in self._move_snapshot:
                new = (node.x, node.y)
                if new != old:
                    changed.append((node, old, new))
            if changed:
                self.undo_stack.push(MoveNodesCommand(self, changed))
                self.modified.emit()
            self._move_snapshot = []
