# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Graph data model — Graph, Node, Edge, Group and StickyNote.

Nodes are polymorphic ($type-tagged), identified by GUID strings; edges
reference nodes by GUID. Ports are *flow* connectors only and are declared per node class as PortSpec lists.
Pan/zoom of the editor view is persisted with the graph.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Iterable

from polytess.core.metadata import get_meta, meta, register_type
from polytess.core.serialization import from_data, to_data
from polytess.core.variables import ListVariables, NameVariables


def new_guid() -> str:
    return uuid.uuid4().hex


class PortSpec:
    """Declarative port description.

    direction: 'in' | 'out'; vertical ports render top/bottom.
    """

    def __init__(self, name: str, direction: str, vertical: bool = False,
                 allow_multiple: bool | None = None, label: str = ""):
        self.name = name
        self.direction = direction
        self.vertical = vertical
        # defaults: inputs single, outputs multiple
        self.allow_multiple = allow_multiple if allow_multiple is not None \
            else (direction == "out")
        self.label = label or name


@meta(title="Node", icon="node", hidden=True)
class Node:
    """BaseNode: guid, custom name, position/size, flags + payload."""

    PORTS: tuple[PortSpec, ...] = ()
    deletable: bool = True
    renamable: bool = True
    accent: str = "blue"        # color token for the title bar

    def __init__(self):
        self.guid: str = new_guid()
        self.custom_name: str = ""
        self.x: float = 0.0
        self.y: float = 0.0
        self.width: float = 220.0
        self.enabled: bool = True
        self.expanded: bool = True
        self.breakpoint: bool = False   # pause execution when this node starts

    # ---- presentation ------------------------------------------------------ #

    @property
    def default_name(self) -> str:
        return get_meta(type(self)).title

    @property
    def name(self) -> str:
        return self.custom_name or self.default_name

    @property
    def icon(self) -> str:
        return get_meta(type(self)).icon

    def ports(self, direction: str | None = None) -> list[PortSpec]:
        specs = list(self.PORTS)
        if direction:
            specs = [p for p in specs if p.direction == direction]
        return specs

    def port(self, name: str) -> PortSpec | None:
        for spec in self.PORTS:
            if spec.name == name:
                return spec
        return None

    @property
    def counter(self) -> int:
        """Number badge shown in the title bar (actions/conditions count)."""
        return 0

    def content_lines(self) -> list:
        """Items previewed in the expanded node body (PolymorphicItems)."""
        return []

    # ---- execution (overridden per node type) ------------------------------- #

    async def process(self, ctx, processor) -> None:
        await processor.run_children(self, "out", ctx)


@meta(title="Group", hidden=True)
class Group:
    """Group — a colored frame around nodes."""

    def __init__(self, title: str = "Group", x: float = 0, y: float = 0,
                 width: float = 400, height: float = 300, color: str = "#3d7ad9"):
        self.guid: str = new_guid()
        self.title = title
        self.x, self.y, self.width, self.height = x, y, width, height
        self.color = color


@meta(title="Sticky Note", hidden=True)
class StickyNote:
    """StickyNote — a free-floating comment."""

    def __init__(self, title: str = "Note", content: str = "",
                 x: float = 0, y: float = 0, width: float = 200, height: float = 140):
        self.guid: str = new_guid()
        self.title = title
        self.content = content
        self.x, self.y, self.width, self.height = x, y, width, height


@meta(title="Edge", hidden=True)
class Edge:
    """SerializableEdge — source is the *output* side, target the *input*."""

    def __init__(self, src_node: str = "", src_port: str = "out",
                 dst_node: str = "", dst_port: str = "in"):
        self.guid: str = new_guid()
        self.src_node = src_node
        self.src_port = src_port
        self.dst_node = dst_node
        self.dst_port = dst_port

    def __repr__(self):
        return f"<Edge {self.src_node[:6]}:{self.src_port} -> {self.dst_node[:6]}:{self.dst_port}>"


class Graph:
    """A workflow asset: nodes + edges + decorations + graph variables
    + persisted view state (pan/zoom)."""

    FILE_SUFFIX = ".flow.json"

    def __init__(self, name: str = "Workflow"):
        from polytess.graph.lineage import Lineage
        self.name = name
        self.lineage = Lineage()           # branch/revision identity
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self.groups: list[Group] = []
        self.notes: list[StickyNote] = []
        self.variables = NameVariables()   # graph scope
        self.lists = ListVariables()
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.zoom: float = 1.0
        self.path: str = ""                # set when loaded/saved (runtime only)

    # ---- structure -------------------------------------------------------- #

    def node_by_guid(self, guid: str) -> Node | None:
        for node in self.nodes:
            if node.guid == guid:
                return node
        return None

    def add_node(self, node: Node) -> Node:
        self.nodes.append(node)
        return node

    def remove_node(self, node: Node) -> None:
        if not node.deletable:
            return
        self.edges = [e for e in self.edges
                      if e.src_node != node.guid and e.dst_node != node.guid]
        self.nodes = [n for n in self.nodes if n.guid != node.guid]

    def connect(self, src: Node, src_port: str, dst: Node, dst_port: str) -> Edge | None:
        """Connect: honours allow_multiple by auto-disconnecting."""
        sp, dp = src.port(src_port), dst.port(dst_port)
        if sp is None or dp is None or sp.direction != "out" or dp.direction != "in":
            return None
        if src.guid == dst.guid:
            return None
        for edge in self.edges:
            if (edge.src_node, edge.src_port, edge.dst_node, edge.dst_port) == \
                    (src.guid, src_port, dst.guid, dst_port):
                return edge   # already connected
        if not sp.allow_multiple:
            self.edges = [e for e in self.edges
                          if not (e.src_node == src.guid and e.src_port == src_port)]
        if not dp.allow_multiple:
            self.edges = [e for e in self.edges
                          if not (e.dst_node == dst.guid and e.dst_port == dst_port)]
        edge = Edge(src.guid, src_port, dst.guid, dst_port)
        self.edges.append(edge)
        return edge

    def remove_edge(self, edge: Edge) -> None:
        self.edges = [e for e in self.edges if e.guid != edge.guid]

    def out_edges(self, node: Node, port: str | None = None) -> list[Edge]:
        return [e for e in self.edges
                if e.src_node == node.guid and (port is None or e.src_port == port)]

    def in_edges(self, node: Node, port: str | None = None) -> list[Edge]:
        return [e for e in self.edges
                if e.dst_node == node.guid and (port is None or e.dst_port == port)]

    def children(self, node: Node, port: str | None = None) -> list[Node]:
        out: list[Node] = []
        for edge in self.out_edges(node, port):
            child = self.node_by_guid(edge.dst_node)
            if child is not None:
                out.append(child)
        return out

    def nodes_of_type(self, node_type: type) -> Iterable[Node]:
        return (n for n in self.nodes if isinstance(n, node_type))

    def ensure_endpoints(self) -> None:
        """auto-creates a non-deletable Start and Exit node."""
        from polytess.graph.nodes import ExitNode, StartNode
        if not any(isinstance(n, StartNode) for n in self.nodes):
            start = StartNode()
            start.x, start.y = -300.0, 0.0
            self.nodes.insert(0, start)
        if not any(isinstance(n, ExitNode) for n in self.nodes):
            exit_node = ExitNode()
            exit_node.x, exit_node.y = 300.0, 0.0
            self.nodes.append(exit_node)

    # ---- persistence -------------------------------------------------------- #

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "lineage": self.lineage.to_data(),
            "nodes": [to_data(n) for n in self.nodes],
            "edges": [to_data(e) for e in self.edges],
            "groups": [to_data(g) for g in self.groups],
            "notes": [to_data(n) for n in self.notes],
            "variables": to_data(self.variables),
            "lists": to_data(self.lists),
            "pan_x": self.pan_x, "pan_y": self.pan_y, "zoom": self.zoom,
        }

    @classmethod
    def from_data(cls, data: dict) -> "Graph":
        from polytess.graph.lineage import Lineage
        graph = cls(data.get("name", "Workflow"))
        if isinstance(data.get("lineage"), dict):   # older files: fresh id
            graph.lineage = Lineage.from_data(data["lineage"])
        graph.nodes = [from_data(n) for n in data.get("nodes", [])]
        graph.edges = [from_data(e) for e in data.get("edges", [])]
        graph.groups = [from_data(g) for g in data.get("groups", [])]
        graph.notes = [from_data(n) for n in data.get("notes", [])]
        graph.variables = from_data(data["variables"]) if "variables" in data else NameVariables()
        graph.lists = from_data(data["lists"]) if "lists" in data else ListVariables()
        graph.pan_x = data.get("pan_x", 0.0)
        graph.pan_y = data.get("pan_y", 0.0)
        graph.zoom = data.get("zoom", 1.0)
        return graph

    def save(self, path: str) -> None:
        data = to_data(self)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        self.path = os.path.abspath(path)

    @classmethod
    def load(cls, path: str) -> "Graph":
        with open(path, encoding="utf-8") as fh:
            graph = from_data(json.load(fh))
        if not isinstance(graph, Graph):
            raise ValueError(f"{path} is not a polytess graph file")
        graph.path = os.path.abspath(path)
        return graph


register_type(Graph)
