# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Variable reference search — where is a variable / list / table used in a
graph, and is it read or written there?

Walks every node payload (instructions, conditions, branches, events,
property sources, nested lists) and collects references:

- PropertyGet sources (GetGraphVariable, GetListElement, GetTableCell, …) -> read
- PropertySet sources (SetGraphVariable, SetListElement, …)              -> write
- {name} placeholders in Formatted String/Path templates                 -> read
- plain instruction fields (list_name, table_name, target_table, …)
  classified via a known-attribute table + naming heuristics
"""

from __future__ import annotations

from dataclasses import dataclass

from polytess.core.conditions import Branch, BranchList, ConditionList
from polytess.core.instructions import InstructionList
from polytess.core.metadata import get_meta
from polytess.core.polymorphic import PolymorphicItem
from polytess.core.properties import PropertyGet, PropertySet

# (class name, attribute) -> access; "" = skip (not a variable reference).
# Most list/table references live in property sources now (handled by the
# PropertyGet/Set branch) — only plain string fields remain here.
_KNOWN_ATTRS: dict[tuple[str, str], str] = {
    ("LoopTable", "row_index_to"): "write",
    ("VariableExists", "name"): "read",
}

_NAME_ATTRS = ("name", "list_name", "table_name", "row_index_to")

_TEMPLATE_ATTRS = ("template",)


@dataclass
class Reference:
    node_guid: str
    node_name: str
    location: str      # item title / path inside the node
    access: str        # "read" | "write" | "read/write"
    detail: str        # source/instruction type + attribute
    scope: str         # "graph" | "global" | "?"


def _heuristic_access(attr: str) -> str:
    if attr.endswith("_to") or attr.startswith("target"):
        return "write"
    return "read"


def _source_scope(obj) -> str:
    cls_name = type(obj).__name__
    if "Global" in cls_name:
        return "global"
    if "Graph" in cls_name:
        return "graph"
    scope = getattr(obj, "scope", None)
    if scope in ("graph", "global"):
        return scope
    return "?"


def _title_of(item) -> str:
    try:
        return item.title
    except Exception:
        return get_meta(type(item)).title


class _Walker:

    def __init__(self, name: str, scope: str):
        self.name = name
        self.scope = scope       # "graph" | "global" | "any"
        self.refs: list[Reference] = []
        self._tokens = ("{" + name + "}", "{" + name + ":",
                        "#" + name + "#", "{{" + name + "}}")
        self._node = None
        self._item_title = ""

    # -- helpers --------------------------------------------------------------- #

    def _scope_matches(self, ref_scope: str) -> bool:
        return self.scope == "any" or ref_scope in ("?", self.scope)

    def _add(self, access: str, detail: str, ref_scope: str) -> None:
        if not self._scope_matches(ref_scope):
            return
        self.refs.append(Reference(
            node_guid=self._node.guid, node_name=self._node.name,
            location=self._item_title, access=access, detail=detail,
            scope=ref_scope))

    def _check_template(self, text: str, detail: str) -> None:
        if isinstance(text, str) and any(token in text for token in self._tokens):
            self._add("read", detail, "?")

    # -- object scan ------------------------------------------------------------ #

    def scan_object(self, obj, path: str, seen: set) -> None:
        if obj is None or id(obj) in seen:
            return
        seen.add(id(obj))

        if isinstance(obj, (PropertyGet, PropertySet)):
            source = obj.source
            if source is None:
                return
            access = "write" if isinstance(obj, PropertySet) else "read"
            cls_name = type(source).__name__
            for attr in _NAME_ATTRS:
                if getattr(source, attr, None) == self.name:
                    self._add(access, f"{cls_name}.{attr}", _source_scope(source))
            # the wrapper branch fully handles the source: check remaining
            # string attrs for template placeholders and recurse only into
            # nested properties (no generic re-scan -> no duplicates)
            for attr, value in list(vars(source).items()):
                if attr.startswith("_"):
                    continue
                if isinstance(value, str) and attr not in _NAME_ATTRS:
                    self._check_template(value, f"{cls_name}.{attr}")
                elif isinstance(value, (PropertyGet, PropertySet)):
                    self.scan_object(value, path, seen)
            return

        if isinstance(obj, InstructionList):
            for child in obj.instructions:
                self.scan_item(child, path, seen)
            return
        if isinstance(obj, ConditionList):
            for child in obj.conditions:
                self.scan_item(child, path, seen)
            return
        if isinstance(obj, BranchList):
            for child in obj.branches:
                self.scan_item(child, path, seen)
            return

        if isinstance(obj, PolymorphicItem) or hasattr(obj, "__dict__"):
            cls_name = type(obj).__name__
            item_scope = getattr(obj, "scope", None)
            ref_scope = item_scope if item_scope in ("graph", "global") else "?"
            for attr, value in list(vars(obj).items()):
                if attr.startswith("_"):
                    continue
                if isinstance(value, str) and value == self.name \
                        and attr in _NAME_ATTRS:
                    access = _KNOWN_ATTRS.get((cls_name, attr)) \
                        or _heuristic_access(attr)
                    self._add(access, f"{cls_name}.{attr}", ref_scope)
                elif isinstance(value, str):
                    self._check_template(value, f"{cls_name}.{attr}")
                elif isinstance(value, (PropertyGet, PropertySet, InstructionList,
                                        ConditionList, BranchList, Branch,
                                        PolymorphicItem)):
                    self.scan_object(value, f"{path}.{attr}", seen)

    def scan_item(self, item, path: str, seen: set) -> None:
        previous = self._item_title
        self._item_title = _title_of(item)
        self.scan_object(item, path, seen)
        self._item_title = previous

    def scan_node(self, node) -> None:
        self._node = node
        self._item_title = "(node)"
        seen: set = set()
        for attr, value in list(vars(node).items()):
            if attr.startswith("_") or attr in ("guid", "custom_name"):
                continue
            if isinstance(value, InstructionList):
                for item in value.instructions:
                    self.scan_item(item, attr, seen)
            elif isinstance(value, ConditionList):
                for item in value.conditions:
                    self.scan_item(item, attr, seen)
            elif isinstance(value, BranchList):
                for item in value.branches:
                    self.scan_item(item, attr, seen)
            elif isinstance(value, PolymorphicItem):        # e.g. TriggerNode.event
                self.scan_item(value, attr, seen)
            elif isinstance(value, str):
                self._item_title = "(node)"
                self._check_template(value, f"{type(node).__name__}.{attr}")


def find_references(graph, name: str, scope: str = "any") -> list[Reference]:
    """All references to variable/list/table *name* in *graph*.

    scope: "graph" | "global" | "any" — sources whose scope is undeterminable
    (e.g. template placeholders) are always included, marked '?'."""
    walker = _Walker(name, scope)
    for node in graph.nodes:
        walker.scan_node(node)
    return walker.refs


class _RenameWalker:
    """Same traversal as _Walker, but rewrites references in place."""

    def __init__(self, old: str, new: str, scope: str):
        self.old = old
        self.new = new
        self.scope = scope
        self.count = 0
        # template token pairs mirror _Walker._tokens
        self._token_pairs = [
            ("{" + old + "}", "{" + new + "}"),
            ("{" + old + ":", "{" + new + ":"),
            ("#" + old + "#", "#" + new + "#"),
            ("{{" + old + "}}", "{{" + new + "}}"),
        ]

    def _scope_matches(self, ref_scope: str) -> bool:
        return self.scope == "any" or ref_scope in ("?", self.scope)

    def _rewrite_template(self, text: str):
        """(new_text, changed) with every placeholder token renamed."""
        changed = False
        for old_token, new_token in self._token_pairs:
            if old_token in text:
                text = text.replace(old_token, new_token)
                changed = True
        return text, changed

    def rewrite_object(self, obj, seen: set) -> None:
        if obj is None or id(obj) in seen:
            return
        seen.add(id(obj))

        if isinstance(obj, (PropertyGet, PropertySet)):
            source = obj.source
            if source is None:
                return
            for attr in _NAME_ATTRS:
                if getattr(source, attr, None) == self.old \
                        and self._scope_matches(_source_scope(source)):
                    setattr(source, attr, self.new)
                    self.count += 1
            for attr, value in list(vars(source).items()):
                if attr.startswith("_"):
                    continue
                if isinstance(value, str) and attr not in _NAME_ATTRS:
                    new_text, changed = self._rewrite_template(value)
                    if changed:
                        setattr(source, attr, new_text)
                        self.count += 1
                elif isinstance(value, (PropertyGet, PropertySet)):
                    self.rewrite_object(value, seen)
            return

        if isinstance(obj, InstructionList):
            for child in obj.instructions:
                self.rewrite_object(child, seen)
            return
        if isinstance(obj, ConditionList):
            for child in obj.conditions:
                self.rewrite_object(child, seen)
            return
        if isinstance(obj, BranchList):
            for child in obj.branches:
                self.rewrite_object(child, seen)
            return

        if isinstance(obj, PolymorphicItem) or hasattr(obj, "__dict__"):
            item_scope = getattr(obj, "scope", None)
            ref_scope = item_scope if item_scope in ("graph", "global") else "?"
            for attr, value in list(vars(obj).items()):
                if attr.startswith("_"):
                    continue
                if isinstance(value, str) and value == self.old \
                        and attr in _NAME_ATTRS:
                    if self._scope_matches(ref_scope):
                        setattr(obj, attr, self.new)
                        self.count += 1
                elif isinstance(value, str):
                    new_text, changed = self._rewrite_template(value)
                    if changed:
                        setattr(obj, attr, new_text)
                        self.count += 1
                elif isinstance(value, (PropertyGet, PropertySet,
                                        InstructionList, ConditionList,
                                        BranchList, Branch, PolymorphicItem)):
                    self.rewrite_object(value, seen)

    def rewrite_node(self, node) -> None:
        seen: set = set()
        for attr, value in list(vars(node).items()):
            if attr.startswith("_") or attr in ("guid", "custom_name"):
                continue
            if isinstance(value, (InstructionList, ConditionList, BranchList,
                                  PolymorphicItem)):
                self.rewrite_object(value, seen)
            elif isinstance(value, str):
                new_text, changed = self._rewrite_template(value)
                if changed:
                    setattr(node, attr, new_text)
                    self.count += 1


def rename_references(graph, old: str, new: str, scope: str = "any") -> int:
    """Rewrite every reference to variable/list/table *old* in *graph* to
    *new* — name attributes of property sources and instructions plus
    ``{old}``-style template placeholders. Returns the number of rewritten
    references. Renaming a variable together with this keeps all nodes
    working (references go by name; see NameVariables.rename)."""
    walker = _RenameWalker(old, new, scope)
    for node in graph.nodes:
        walker.rewrite_node(node)
    return walker.count
