# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""QUndoStack commands for graph structure edits (add/remove/move/connect)."""

from __future__ import annotations

from PySide6.QtGui import QUndoCommand


class AddNodeCommand(QUndoCommand):

    def __init__(self, scene, node):
        super().__init__(f"Add {node.name}")
        self.scene = scene
        self.node = node

    def redo(self):
        self.scene.graph.add_node(self.node)
        self.scene.sync_items()

    def undo(self):
        self.scene.graph.remove_node(self.node)
        self.scene.sync_items()


class RemoveSelectionCommand(QUndoCommand):
    """Removes nodes (with their edges), selected edges, groups and notes."""

    def __init__(self, scene, nodes, edges, groups=(), notes=()):
        super().__init__("Delete selection")
        self.scene = scene
        self.nodes = [n for n in nodes if n.deletable]
        self.groups = list(groups)
        self.notes = list(notes)
        graph = scene.graph
        guids = {n.guid for n in self.nodes}
        implied = [e for e in graph.edges
                   if e.src_node in guids or e.dst_node in guids]
        self.edges = list({id(e): e for e in list(edges) + implied}.values())

    def redo(self):
        graph = self.scene.graph
        for edge in self.edges:
            graph.remove_edge(edge)
        for node in self.nodes:
            graph.nodes = [n for n in graph.nodes if n.guid != node.guid]
        group_ids = {g.guid for g in self.groups}
        note_ids = {n.guid for n in self.notes}
        graph.groups = [g for g in graph.groups if g.guid not in group_ids]
        graph.notes = [n for n in graph.notes if n.guid not in note_ids]
        self.scene.sync_items()

    def undo(self):
        graph = self.scene.graph
        graph.nodes.extend(self.nodes)
        graph.edges.extend(self.edges)
        graph.groups.extend(self.groups)
        graph.notes.extend(self.notes)
        self.scene.sync_items()


class AddDecorationCommand(QUndoCommand):
    """Adds a Group or StickyNote."""

    def __init__(self, scene, model, collection_name: str):
        super().__init__("Add group" if collection_name == "groups" else "Add note")
        self.scene = scene
        self.model = model
        self.collection_name = collection_name

    def _collection(self):
        return getattr(self.scene.graph, self.collection_name)

    def redo(self):
        self._collection().append(self.model)
        self.scene.sync_items()

    def undo(self):
        collection = self._collection()
        setattr(self.scene.graph, self.collection_name,
                [m for m in collection if m.guid != self.model.guid])
        self.scene.sync_items()


class ConnectCommand(QUndoCommand):

    def __init__(self, scene, src, src_port, dst, dst_port):
        super().__init__("Connect")
        self.scene = scene
        self.args = (src, src_port, dst, dst_port)
        self.edge = None
        self.removed: list = []

    def redo(self):
        graph = self.scene.graph
        before = list(graph.edges)
        self.edge = graph.connect(*self.args[:2], *self.args[2:])
        self.removed = [e for e in before if e not in graph.edges]
        self.scene.sync_items()

    def undo(self):
        graph = self.scene.graph
        if self.edge is not None:
            graph.remove_edge(self.edge)
        graph.edges.extend(self.removed)
        self.scene.sync_items()


class RemoveEdgeCommand(QUndoCommand):

    def __init__(self, scene, edge):
        super().__init__("Disconnect")
        self.scene = scene
        self.edge = edge

    def redo(self):
        self.scene.graph.remove_edge(self.edge)
        self.scene.sync_items()

    def undo(self):
        self.scene.graph.edges.append(self.edge)
        self.scene.sync_items()


class MoveNodesCommand(QUndoCommand):
    """positions: list of (node, (old_x, old_y), (new_x, new_y))"""

    def __init__(self, scene, positions):
        super().__init__("Move")
        self.scene = scene
        self.positions = positions
        self._first = True

    def redo(self):
        if self._first:           # positions already applied by the drag
            self._first = False
            return
        for node, _old, new in self.positions:
            node.x, node.y = new
        self.scene.sync_positions()

    def undo(self):
        for node, old, _new in self.positions:
            node.x, node.y = old
        self.scene.sync_positions()


class PasteCommand(QUndoCommand):

    def __init__(self, scene, nodes, edges):
        super().__init__("Paste")
        self.scene = scene
        self.nodes = nodes
        self.edges = edges

    def redo(self):
        self.scene.graph.nodes.extend(self.nodes)
        self.scene.graph.edges.extend(self.edges)
        self.scene.sync_items()

    def undo(self):
        graph = self.scene.graph
        guids = {n.guid for n in self.nodes}
        edge_ids = {e.guid for e in self.edges}
        graph.nodes = [n for n in graph.nodes if n.guid not in guids]
        graph.edges = [e for e in graph.edges if e.guid not in edge_ids]
        self.scene.sync_items()
