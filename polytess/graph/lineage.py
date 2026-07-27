# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Flow lifecycle — branches, revisions, history and structural diffs.

Every graph carries a ``lineage`` block in its ``.flow.json``:

    "lineage": {"flow_id": "<uuid>", "branch": "main", "revision": 4,
                "parent_branch": "", "parent_revision": 0}

``flow_id`` identifies the flow *family* and never changes — branches and
revisions all share it, so the relationship survives copying and renaming.
Branching copies the graph (same node GUIDs, which is what makes diffs
precise), points ``parent_*`` at the source and starts at revision 1.
Saving through the studio bumps the revision and files a snapshot under
``.history/<flow_id>/<branch>-r<rev>.flow.json`` next to the flow, so no
promoted or overwritten state is ever lost. Everything is plain files —
no external version control involved.
"""

from __future__ import annotations

import json
import os
import uuid

from polytess.core.serialization import from_data, to_data
from polytess.graph.model import Graph


class Lineage:
    """Identity + ancestry of one flow file (no registry entry needed)."""

    def __init__(self):
        self.flow_id: str = uuid.uuid4().hex
        self.branch: str = "main"
        self.revision: int = 0            # bumped on every studio save
        self.parent_branch: str = ""
        self.parent_revision: int = 0

    @property
    def tag(self) -> str:
        """Short display tag, e.g. ``main·r4`` or ``test-modes·r2``."""
        return f"{self.branch}·r{self.revision}"

    @property
    def has_parent(self) -> bool:
        return bool(self.parent_branch)

    def to_data(self) -> dict:
        return {"flow_id": self.flow_id, "branch": self.branch,
                "revision": self.revision,
                "parent_branch": self.parent_branch,
                "parent_revision": self.parent_revision}

    @classmethod
    def from_data(cls, data: dict) -> "Lineage":
        lineage = cls()
        lineage.flow_id = str(data.get("flow_id") or lineage.flow_id)
        lineage.branch = str(data.get("branch") or "main")
        lineage.revision = int(data.get("revision") or 0)
        lineage.parent_branch = str(data.get("parent_branch") or "")
        lineage.parent_revision = int(data.get("parent_revision") or 0)
        return lineage


# --------------------------------------------------------------------------- #
# operations
# --------------------------------------------------------------------------- #

def clone_graph(graph: Graph) -> Graph:
    """Deep copy via serialization round-trip — node GUIDs are preserved."""
    return from_data(json.loads(json.dumps(to_data(graph))))


def branch_graph(graph: Graph, branch_name: str) -> Graph:
    """A new branch of *graph*: same family, parent points at the source."""
    branch = clone_graph(graph)
    branch.lineage = Lineage()
    branch.lineage.flow_id = graph.lineage.flow_id
    branch.lineage.branch = branch_name
    branch.lineage.revision = 0
    branch.lineage.parent_branch = graph.lineage.branch
    branch.lineage.parent_revision = graph.lineage.revision
    return branch


def branch_file_path(source_path: str, branch_name: str) -> str:
    """``pipeline.flow.json`` + "test" -> ``pipeline@test.flow.json``."""
    folder = os.path.dirname(source_path)
    stem = os.path.basename(source_path)
    if stem.endswith(Graph.FILE_SUFFIX):
        stem = stem[: -len(Graph.FILE_SUFFIX)]
    stem = stem.split("@", 1)[0]
    return os.path.join(folder, f"{stem}@{branch_name}{Graph.FILE_SUFFIX}")


def history_dir(flow_path: str, flow_id: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(flow_path)),
                        ".history", flow_id)


def save_with_history(graph: Graph, path: str) -> None:
    """Studio save: bump the revision and file an immutable snapshot."""
    graph.lineage.revision += 1
    graph.save(path)
    folder = history_dir(path, graph.lineage.flow_id)
    os.makedirs(folder, exist_ok=True)
    snapshot = os.path.join(
        folder, f"{graph.lineage.branch}-r{graph.lineage.revision}"
                f"{Graph.FILE_SUFFIX}")
    with open(path, encoding="utf-8") as src, \
            open(snapshot, "w", encoding="utf-8") as dst:
        dst.write(src.read())


def list_history(flow_path: str, flow_id: str) -> list[str]:
    """Snapshot paths for this family, newest first."""
    folder = history_dir(flow_path, flow_id)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    paths = [os.path.join(folder, n) for n in names
             if n.endswith(Graph.FILE_SUFFIX)]
    return sorted(paths, key=os.path.getmtime, reverse=True)


def promote_graph(branch: Graph, target_path: str) -> Graph:
    """Replace the parent flow at *target_path* with the branch content.

    The parent's current state is snapshotted first (nothing is lost).
    The promoted graph keeps the PARENT's branch name and continues its
    revision count; ``parent_*`` records where the content came from."""
    target = Graph.load(target_path)
    if target.lineage.flow_id != branch.lineage.flow_id:
        raise ValueError("Different flow families — refusing to promote "
                         f"({target.lineage.flow_id[:8]} vs "
                         f"{branch.lineage.flow_id[:8]}).")
    save_with_history(target, target_path)         # snapshot old parent state

    promoted = clone_graph(branch)
    promoted.lineage = Lineage()
    promoted.lineage.flow_id = target.lineage.flow_id
    promoted.lineage.branch = target.lineage.branch
    promoted.lineage.revision = target.lineage.revision
    promoted.lineage.parent_branch = branch.lineage.branch
    promoted.lineage.parent_revision = branch.lineage.revision
    save_with_history(promoted, target_path)
    return promoted


# --------------------------------------------------------------------------- #
# structural diff
# --------------------------------------------------------------------------- #

class DiffEntry(str):
    """A diff line that behaves like its display text but knows which
    node it belongs to — the GUI uses ``guid`` to jump to the node."""

    guid: str = ""

    def __new__(cls, text: str, guid: str = ""):
        entry = super().__new__(cls, text)
        entry.guid = guid
        return entry


class FlowDiff:
    def __init__(self):
        self.nodes_added: list[DiffEntry] = []      # display names
        self.nodes_removed: list[DiffEntry] = []
        self.nodes_changed: list[DiffEntry] = []    # "name: field a -> b"
        self.edges_added: list[DiffEntry] = []
        self.edges_removed: list[DiffEntry] = []
        self.variables_changed: list[DiffEntry] = []

    @property
    def is_empty(self) -> bool:
        return not (self.nodes_added or self.nodes_removed or
                    self.nodes_changed or self.edges_added or
                    self.edges_removed or self.variables_changed)

    def summary(self) -> str:
        parts = []
        for label, items in (("added", self.nodes_added),
                             ("removed", self.nodes_removed),
                             ("changed", self.nodes_changed)):
            if items:
                parts.append(f"{len(items)} node{'s' if len(items) != 1 else ''} {label}")
        edge_count = len(self.edges_added) + len(self.edges_removed)
        if edge_count:
            parts.append(f"{edge_count} connection{'s' if edge_count != 1 else ''}")
        if self.variables_changed:
            parts.append(f"{len(self.variables_changed)} variables")
        return ", ".join(parts) if parts else "no differences"


def _node_fields(node_data: dict) -> dict:
    skip = {"guid", "x", "y", "width", "expanded"}    # layout is not content
    return {k: v for k, v in node_data.items() if k not in skip}


def _describe_change(name: str, guid: str, old: dict, new: dict) -> list[DiffEntry]:
    lines = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) == new.get(key):
            continue
        entry = f"{name}: {key}"
        old_json = json.dumps(old.get(key), ensure_ascii=False)
        new_json = json.dumps(new.get(key), ensure_ascii=False)
        if len(old_json) + len(new_json) <= 120:
            entry += f"  {old_json} → {new_json}"
        lines.append(DiffEntry(entry, guid))
    return lines


def diff_graphs(base: Graph, other: Graph) -> FlowDiff:
    """What changed from *base* to *other* (matched by node GUID)."""
    diff = FlowDiff()
    base_nodes = {n.guid: n for n in base.nodes}
    other_nodes = {n.guid: n for n in other.nodes}

    for guid, node in other_nodes.items():
        if guid not in base_nodes:
            diff.nodes_added.append(DiffEntry(node.name, guid))
    for guid, node in base_nodes.items():
        if guid not in other_nodes:
            diff.nodes_removed.append(DiffEntry(node.name, guid))
    for guid in base_nodes.keys() & other_nodes.keys():
        old = _node_fields(to_data(base_nodes[guid]))
        new = _node_fields(to_data(other_nodes[guid]))
        if old != new:
            diff.nodes_changed += _describe_change(
                other_nodes[guid].name, guid, old, new)

    def edge_entry(graph: Graph, edge) -> DiffEntry:
        src = graph.node_by_guid(edge.src_node)
        dst = graph.node_by_guid(edge.dst_node)
        return DiffEntry(f"{src.name if src else '?'}:{edge.src_port} → "
                         f"{dst.name if dst else '?'}", edge.src_node)

    base_edges = {(e.src_node, e.src_port, e.dst_node): e for e in base.edges}
    other_edges = {(e.src_node, e.src_port, e.dst_node): e for e in other.edges}
    for key, edge in other_edges.items():
        if key not in base_edges:
            diff.edges_added.append(edge_entry(other, edge))
    for key, edge in base_edges.items():
        if key not in other_edges:
            diff.edges_removed.append(edge_entry(base, edge))

    base_vars = {v.name: to_data(v) for v in base.variables}
    other_vars = {v.name: to_data(v) for v in other.variables}
    for name in sorted(set(base_vars) | set(other_vars)):
        if base_vars.get(name) != other_vars.get(name):
            diff.variables_changed.append(DiffEntry(name))
    return diff


def find_parent_path(branch_path: str) -> str:
    """Default parent file for ``pipeline@test.flow.json`` -> ``pipeline.flow.json``."""
    folder = os.path.dirname(branch_path)
    stem = os.path.basename(branch_path)
    if stem.endswith(Graph.FILE_SUFFIX):
        stem = stem[: -len(Graph.FILE_SUFFIX)]
    if "@" not in stem:
        return ""
    candidate = os.path.join(folder, stem.split("@", 1)[0] + Graph.FILE_SUFFIX)
    return candidate if os.path.isfile(candidate) else ""
