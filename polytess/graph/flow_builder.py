# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Build a Graph from the flow assistant's simplified JSON description.

The assistant describes a workflow in a compact schema (see FLOW_SCHEMA_DOC);
this module turns it into a real Graph, validates every referenced building
block against the registry and reports what is missing — including a
ready-to-paste prompt for the code assistant to create the missing blocks.

Schema example::

    {
      "name": "Modal Reduction",
      "variables": [{"name": "deck", "type": "string", "value": "MR_001"}],
      "lists":     [{"name": "paths", "type": "path", "items": []}],
      "nodes": [
        {"id": "prep", "kind": "actions", "name": "Prepare",
         "instructions": [
            {"type": "CreateFolder", "params": {"path": "results"}},
            {"type": "SetString", "params": {"name": "deck",
                                             "value": {"var": "deck"}}}]},
        {"id": "check", "kind": "conditions", "mode": "and",
         "conditions": [{"type": "FileExists",
                         "params": {"path": "results/out.inp"}}]}
      ],
      "edges": [
        {"from": "start", "to": "prep"},
        {"from": "prep", "to": "check"},
        {"from": "check", "port": "success", "to": "exit"},
        {"from": "check", "port": "fail", "to": "prep"}
      ]
    }

Param values: plain values set constant sources; ``{"var": "name"}`` /
``{"global": "name"}`` bind graph/global variables (lists and tables use the
matching list/table sources automatically); ``{"template": "x_{n}.inp"}``
uses a formatted string/path; ``{"target": true}`` reads the loop target.
For Property*Set* write-targets a plain string is the graph-variable name.
"""

from __future__ import annotations

from polytess.core.conditions import Branch, BranchList, Condition, ConditionList
from polytess.core.events import Event
from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import get_meta, iter_subclasses
from polytess.core.properties import (GetConstantList, GetGlobalList,
                                    GetGlobalTable, GetGlobalVariable,
                                    GetGraphList, GetGraphTable,
                                    GetGraphVariable, GetNone, GetPathFormat,
                                    GetStringFormat, GetTarget, PropertyGet,
                                    PropertyGetList, PropertyGetPath,
                                    PropertyGetTable, PropertySet,
                                    SetGlobalList, SetGlobalTable,
                                    SetGlobalVariable, SetGraphList,
                                    SetGraphTable, SetGraphVariable, SetNone)
from polytess.graph.model import Graph, Group, StickyNote
from polytess.graph.nodes import (ActionsNode, BranchNode, ConditionsNode,
                                ExitNode, StartNode, SubGraphNode, TriggerNode)


class BuildResult:
    """Outcome of build_flow: the graph plus everything worth reporting."""

    def __init__(self):
        self.graph: Graph | None = None
        self.missing: list[str] = []     # unknown building-block type names
        self.warnings: list[str] = []    # non-fatal issues (bad params, ...)
        self.errors: list[str] = []      # fatal issues (schema broken)

    @property
    def ok(self) -> bool:
        return self.graph is not None and not self.errors and not self.missing


# ---- registry lookup --------------------------------------------------------- #

def _block_lookup() -> dict[str, type]:
    """Class name AND meta title (lowercased) -> class, for all blocks."""
    lookup: dict[str, type] = {}
    for base in (Instruction, Condition, Event):
        for cls in iter_subclasses(base, include_hidden=True):
            lookup[cls.__name__.lower()] = cls
            title = get_meta(cls).title
            if title:
                lookup[title.lower()] = cls
    return lookup


def _field_kind(value) -> str:
    """Human/LLM-readable kind label for a block field."""
    if isinstance(value, PropertyGetTable):
        return "table"
    if isinstance(value, PropertyGetList):
        return "list"
    if isinstance(value, PropertyGet):
        return value.value_type
    if isinstance(value, PropertySet):
        return f"set:{value.value_type}"
    if isinstance(value, InstructionList):
        return "instructions"
    if isinstance(value, ConditionList):
        return "conditions"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def build_flow_registry_summary() -> str:
    """Every registered block with its fields — the flow agent's knowledge
    of what exists and how to parameterize it."""
    from polytess.core.metadata import get_field_help
    sections = (("Instructions", Instruction), ("Conditions", Condition),
                ("Events (for trigger nodes)", Event))
    parts = ["## Available building blocks (registry) — class, purpose, "
             "then one line per field: name: kind (choices) — meaning"]
    for label, base in sections:
        parts.append(f"### {label}")
        for cls in sorted(iter_subclasses(base),
                          key=lambda c: get_meta(c).category):
            m = get_meta(cls)
            description = (m.description or "").split(". ")[0][:100]
            parts.append(f"- {cls.__name__} [{m.title}] — {description}")
            try:
                instance = cls()
            except Exception:
                continue
            helps = get_field_help(cls)
            choices = getattr(cls, "FIELD_CHOICES", {}) or {}
            for attr, value in vars(instance).items():
                if attr.startswith("_"):
                    continue
                line = f"    {attr}: {_field_kind(value)}"
                if attr in choices:
                    line += f" ({'|'.join(choices[attr])})"
                help_text = helps.get(attr, "").strip()
                if help_text:
                    line += f" — {help_text}"
                parts.append(line)
    return "\n".join(parts)


# ---- parameter application ----------------------------------------------------- #

def _get_source_for(prop, spec: dict):
    """PropertySource instance for a {"var"/"global"/"template"/"target"} spec."""
    if "var" in spec:
        name = str(spec["var"])
        if isinstance(prop, PropertyGetTable):
            return GetGraphTable(name)
        if isinstance(prop, PropertyGetList):
            return GetGraphList(name)
        return GetGraphVariable(name)
    if "global" in spec:
        name = str(spec["global"])
        if isinstance(prop, PropertyGetTable):
            return GetGlobalTable(name)
        if isinstance(prop, PropertyGetList):
            return GetGlobalList(name)
        return GetGlobalVariable(name)
    if "template" in spec:
        template = str(spec["template"])
        return (GetPathFormat(template) if isinstance(prop, PropertyGetPath)
                else GetStringFormat(template))
    if spec.get("target"):
        return GetTarget()
    return None


def _set_source_for(prop: PropertySet, value):
    """SetSource instance for a write-target param (string = graph variable,
    {"global": name} = global variable)."""
    scope_global = isinstance(value, dict) and "global" in value
    name = str(value["global"] if scope_global else
               value["var"] if isinstance(value, dict) and "var" in value
               else value)
    if prop.value_type == "list":
        return (SetGlobalList if scope_global else SetGraphList)(name)
    if prop.value_type == "table":
        return (SetGlobalTable if scope_global else SetGraphTable)(name)
    return (SetGlobalVariable if scope_global else SetGraphVariable)(name)


def _apply_params(obj, params: dict, result: BuildResult, where: str) -> None:
    for key, value in (params or {}).items():
        if not hasattr(obj, key) or key.startswith("_"):
            result.warnings.append(f"{where}: unknown field {key!r} — skipped")
            continue
        current = getattr(obj, key)
        try:
            if isinstance(current, PropertyGet):
                if isinstance(value, dict):
                    source = _get_source_for(current, value)
                    if source is None:
                        result.warnings.append(
                            f"{where}.{key}: unsupported value spec {value!r}")
                        continue
                    setattr(obj, key, type(current)(source))
                else:
                    setattr(obj, key, type(current)(value))
            elif isinstance(current, PropertySet):
                setattr(obj, key, type(current)(_set_source_for(current, value)))
            elif isinstance(current, InstructionList):
                _fill_instruction_list(current, value, result, f"{where}.{key}")
            elif isinstance(current, ConditionList):
                _fill_condition_list(current, value, result, f"{where}.{key}")
            elif isinstance(current, bool):
                setattr(obj, key, bool(value))
            elif isinstance(current, int) and not isinstance(current, bool):
                setattr(obj, key, int(value))
            elif isinstance(current, float):
                setattr(obj, key, float(value))
            else:
                setattr(obj, key, value if not isinstance(current, str)
                        else str(value))
        except Exception as exc:
            result.warnings.append(f"{where}.{key}: {exc}")


def _make_block(spec: dict, base: type, lookup: dict[str, type],
                result: BuildResult, where: str):
    type_name = str(spec.get("type", "")).strip()
    cls = lookup.get(type_name.lower())
    if cls is None or not issubclass(cls, base):
        if type_name and type_name not in result.missing:
            result.missing.append(type_name)
        return None
    block = cls()
    _apply_params(block, spec.get("params", {}), result, f"{where}[{type_name}]")
    return block


def _fill_instruction_list(target: InstructionList, specs, result, where) -> None:
    lookup = _block_lookup()
    for spec in specs or []:
        block = _make_block(spec, Instruction, lookup, result, where)
        if block is not None:
            target.instructions.append(block)


def _fill_condition_list(target: ConditionList, specs, result, where) -> None:
    lookup = _block_lookup()
    for spec in specs or []:
        block = _make_block(spec, Condition, lookup, result, where)
        if block is not None:
            target.conditions.append(block)


# ---- graph building -------------------------------------------------------------- #

_X_STEP, _Y_STEP, _X_START = 300.0, 190.0, -300.0


def _layout(graph: Graph) -> None:
    """Left-to-right columns by BFS depth from the entry nodes."""
    depth: dict[str, int] = {}
    frontier = [n for n in graph.nodes if isinstance(n, (StartNode, TriggerNode))]
    for node in frontier:
        depth[node.guid] = 0
    while frontier:
        next_frontier = []
        for node in frontier:
            for child in graph.children(node):
                if child.guid in depth:      # first reach wins — flows may
                    continue                 # contain cycles (retry edges)
                depth[child.guid] = depth[node.guid] + 1
                next_frontier.append(child)
        frontier = next_frontier
    max_depth = max(depth.values(), default=0)
    rows: dict[int, int] = {}
    for node in graph.nodes:
        column = depth.get(node.guid, max_depth + 1)
        if isinstance(node, ExitNode):
            column = max(column, max_depth + 1)
        row = rows.get(column, 0)
        rows[column] = row + 1
        node.x = _X_START + column * _X_STEP
        node.y = row * _Y_STEP


def build_flow(data: dict) -> BuildResult:
    """Simplified flow description -> Graph (see module docstring)."""
    result = BuildResult()
    if not isinstance(data, dict):
        result.errors.append("Flow description must be a JSON object.")
        return result
    lookup = _block_lookup()
    graph = Graph(str(data.get("name") or "Workflow"))

    for spec in data.get("variables") or []:
        try:
            var = graph.variables.declare(str(spec["name"]),
                                          str(spec.get("type", "string")),
                                          spec.get("value"))
            var.group = str(spec.get("group", "") or "")
        except Exception as exc:
            result.warnings.append(f"variable {spec!r}: {exc}")
    for spec in data.get("lists") or []:
        try:
            graph.lists.declare(str(spec["name"]),
                                str(spec.get("type", "string")),
                                list(spec.get("items") or []))
        except Exception as exc:
            result.warnings.append(f"list {spec!r}: {exc}")

    by_id: dict[str, object] = {}
    positioned: set[str] = set()
    for spec in data.get("nodes") or []:
        node_id = str(spec.get("id") or f"n{len(by_id)}")
        kind = str(spec.get("kind", "actions")).lower()
        where = f"node '{node_id}'"
        if kind == "start":
            node = StartNode()
            _fill_instruction_list(node.instructions,
                                   spec.get("instructions"), result, where)
        elif kind == "exit":
            node = ExitNode()
            _fill_instruction_list(node.instructions,
                                   spec.get("instructions"), result, where)
        elif kind == "actions":
            node = ActionsNode()
            _fill_instruction_list(node.instructions,
                                   spec.get("instructions"), result, where)
        elif kind == "conditions":
            node = ConditionsNode()
            node.check_mode = str(spec.get("mode", "and")).lower()
            _fill_condition_list(node.conditions,
                                 spec.get("conditions"), result, where)
        elif kind == "branch":
            node = BranchNode()
            for branch_spec in spec.get("branches") or []:
                branch = Branch(str(branch_spec.get("name", "Branch")))
                _fill_condition_list(branch.conditions,
                                     branch_spec.get("conditions"),
                                     result, where)
                _fill_instruction_list(branch.instructions,
                                       branch_spec.get("instructions"),
                                       result, where)
                node.branches.branches.append(branch)
        elif kind == "trigger":
            node = TriggerNode()
            event_spec = spec.get("event") or {}
            event = _make_block(event_spec, Event, lookup, result, where)
            node.event = event
        elif kind in ("subworkflow", "subgraph"):
            node = SubGraphNode()
            node.file = str(spec.get("file", ""))
        else:
            result.warnings.append(f"{where}: unknown kind {kind!r} — skipped")
            continue
        if spec.get("name"):
            node.custom_name = str(spec["name"])
        if "x" in spec and "y" in spec:
            try:
                node.x, node.y = float(spec["x"]), float(spec["y"])
                positioned.add(node_id)
            except (TypeError, ValueError):
                result.warnings.append(f"{where}: bad x/y — ignored")
        graph.add_node(node)
        by_id[node_id] = node

    graph.ensure_endpoints()
    start = next(iter(graph.nodes_of_type(StartNode)))
    exit_node = next(iter(graph.nodes_of_type(ExitNode)))
    by_id.setdefault("start", start)
    by_id.setdefault("exit", exit_node)
    by_id.setdefault("end", exit_node)

    for spec in data.get("groups") or []:
        try:
            graph.groups.append(Group(
                title=str(spec.get("title", "Group")),
                x=float(spec.get("x", 0)), y=float(spec.get("y", 0)),
                width=float(spec.get("width", 400)),
                height=float(spec.get("height", 300)),
                color=str(spec.get("color", "#3d7ad9"))))
        except (TypeError, ValueError) as exc:
            result.warnings.append(f"group {spec!r}: {exc}")
    for spec in data.get("notes") or []:
        try:
            graph.notes.append(StickyNote(
                title=str(spec.get("title", "Note")),
                content=str(spec.get("content", "")),
                x=float(spec.get("x", 0)), y=float(spec.get("y", 0)),
                width=float(spec.get("width", 200)),
                height=float(spec.get("height", 140))))
        except (TypeError, ValueError) as exc:
            result.warnings.append(f"note {spec!r}: {exc}")

    for spec in data.get("edges") or []:
        src = by_id.get(str(spec.get("from", "")))
        dst = by_id.get(str(spec.get("to", "")))
        if src is None or dst is None:
            result.warnings.append(f"edge {spec!r}: unknown node id — skipped")
            continue
        out_ports = src.ports("out")
        default_out = out_ports[0].name if out_ports else "out"
        src_port = str(spec.get("port") or default_out)
        dst_port = dst.ports("in")[0].name if dst.ports("in") else "in"
        if src.port(src_port) is None:
            result.warnings.append(
                f"edge {spec!r}: no output port {src_port!r} on "
                f"{src.name} — skipped")
            continue
        if graph.connect(src, src_port, dst, dst_port) is None:
            result.warnings.append(f"edge {spec!r}: could not connect")

    if not positioned:
        _layout(graph)                   # fresh flow: automatic columns
    else:
        # explicit positions win (round-trip of an existing flow keeps
        # the user's layout); park any NEW unpositioned node below
        placed = {node for key, node in by_id.items() if key in positioned}
        max_y = max((n.y for n in placed), default=0.0)
        offset = 0
        for node in graph.nodes:
            if node in placed:
                continue
            if isinstance(node, (StartNode, ExitNode)) \
                    and node not in by_id.values():
                continue                 # implicit endpoints keep defaults
            offset += 1
            node.x = _X_START + offset * _X_STEP
            node.y = max_y + _Y_STEP
    result.graph = graph
    return result


# ---- graph export (inverse of build_flow, for assistant context) ------------------- #

def _export_get_source(source) -> object:
    """PropertySource -> simplified-schema param value (None = default,
    string form = unrepresentable computed source)."""
    if source is None or isinstance(source, GetNone):
        return None
    if isinstance(source, (GetGraphVariable, GetGraphList, GetGraphTable)) \
            and not isinstance(source, (GetGlobalTable,)):
        return {"var": source.name}
    if isinstance(source, (GetGlobalVariable, GetGlobalList, GetGlobalTable)):
        return {"global": source.name}
    if isinstance(source, (GetStringFormat, GetPathFormat)):
        return {"template": source.template}
    if isinstance(source, GetTarget):
        return {"target": True}
    if isinstance(source, GetConstantList):
        return list(source.items)
    if hasattr(source, "value"):             # GetConstantString/Number/...
        return source.value
    return f"<{source.display}>"             # computed source — informative only


def _export_set_source(source) -> object:
    if source is None or isinstance(source, SetNone):
        return None
    if isinstance(source, (SetGlobalVariable, SetGlobalList, SetGlobalTable)):
        return {"global": source.name}
    if isinstance(source, (SetGraphVariable, SetGraphList, SetGraphTable)):
        return source.name
    return f"<{source.display}>"             # computed target — informative only


def _export_params(obj) -> dict:
    """Public fields of a block -> simplified params dict (defaults omitted
    where cheaply detectable, i.e. unset sources and empty strings)."""
    params: dict = {}
    for key, value in vars(obj).items():
        if key.startswith("_"):
            continue
        if isinstance(value, PropertyGet):
            exported = _export_get_source(getattr(value, "source", None))
            if exported is not None and exported != "":
                params[key] = exported
        elif isinstance(value, PropertySet):
            exported = _export_set_source(getattr(value, "source", None))
            if exported is not None and exported != "":
                params[key] = exported
        elif isinstance(value, InstructionList):
            blocks = [_export_block(i) for i in value.instructions]
            if blocks:
                params[key] = blocks
        elif isinstance(value, ConditionList):
            blocks = [_export_block(c) for c in value.conditions]
            if blocks:
                params[key] = blocks
        elif isinstance(value, (bool, int, float)):
            params[key] = value
        elif isinstance(value, str):
            if value:
                params[key] = value
    return params


def _export_block(block) -> dict:
    return {"type": type(block).__name__, "params": _export_params(block)}


def flow_to_data(graph: Graph) -> dict:
    """Serialize a Graph into the assistant's simplified flow schema —
    the inverse of build_flow, lossy for computed property sources (which
    export as informative "<...>" strings). Used to show the assistant
    the currently open flow."""
    data: dict = {"name": graph.name, "variables": [], "lists": [],
                  "nodes": [], "edges": []}
    for var in graph.variables:
        spec = {"name": var.name, "type": var.type_id,
                "value": var.value.get()}
        if getattr(var, "group", ""):
            spec["group"] = var.group
        data["variables"].append(spec)
    for lst in graph.lists:
        data["lists"].append({"name": lst.name, "type": lst.type_id,
                              "items": list(lst.items)})

    ids: dict[str, str] = {}
    counter = 0
    for node in graph.nodes:
        if isinstance(node, StartNode):
            ids[node.guid] = "start"
        elif isinstance(node, ExitNode):
            ids[node.guid] = "exit"
        else:
            counter += 1
            ids[node.guid] = f"n{counter}"

    for node in graph.nodes:
        node_id = ids[node.guid]
        spec: dict = {"id": node_id}
        if isinstance(node, StartNode):
            spec["kind"] = "start"
            blocks = [_export_block(i) for i in node.instructions]
            if blocks:
                spec["instructions"] = blocks
        elif isinstance(node, ExitNode):
            spec["kind"] = "exit"
            blocks = [_export_block(i) for i in node.instructions]
            if blocks:
                spec["instructions"] = blocks
        elif isinstance(node, ActionsNode):
            spec["kind"] = "actions"
            spec["instructions"] = [_export_block(i)
                                    for i in node.instructions]
        elif isinstance(node, ConditionsNode):
            spec["kind"] = "conditions"
            spec["mode"] = node.check_mode
            spec["conditions"] = [_export_block(c) for c in node.conditions]
        elif isinstance(node, BranchNode):
            spec["kind"] = "branch"
            spec["branches"] = [
                {"name": branch.name,
                 "conditions": [_export_block(c)
                                for c in branch.conditions.conditions],
                 "instructions": [_export_block(i)
                                  for i in branch.instructions.instructions]}
                for branch in node.branches.branches]
        elif isinstance(node, TriggerNode):
            spec["kind"] = "trigger"
            if node.event is not None:
                spec["event"] = _export_block(node.event)
        elif isinstance(node, SubGraphNode):
            spec["kind"] = "subworkflow"
            spec["file"] = node.file
        else:
            continue
        if getattr(node, "custom_name", ""):
            spec["name"] = node.custom_name
        spec["x"] = round(node.x, 1)
        spec["y"] = round(node.y, 1)
        data["nodes"].append(spec)

    if graph.groups:
        data["groups"] = [
            {"title": group.title, "x": round(group.x, 1),
             "y": round(group.y, 1), "width": round(group.width, 1),
             "height": round(group.height, 1), "color": group.color}
            for group in graph.groups]
    if graph.notes:
        data["notes"] = [
            {"title": note.title, "content": note.content,
             "x": round(note.x, 1), "y": round(note.y, 1),
             "width": round(note.width, 1), "height": round(note.height, 1)}
            for note in graph.notes]

    for edge in graph.edges:
        src = ids.get(edge.src_node)
        dst = ids.get(edge.dst_node)
        if src is None or dst is None:
            continue
        spec = {"from": src, "to": dst}
        if edge.src_port not in ("out", ""):
            spec["port"] = edge.src_port
        data["edges"].append(spec)
    return data


# ---- missing-block prompt ----------------------------------------------------------- #

def missing_blocks_prompt(missing: list[str], purpose: str = "") -> str:
    """Ready-to-paste prompt for the code assistant to create the blocks
    the flow needs but the registry does not have."""
    if not missing:
        return ""
    blocks = "\n".join(f"- {name}" for name in missing)
    intro = (f"My workflow \"{purpose}\" needs" if purpose
             else "My workflow needs")
    return (f"{intro} the following building blocks that are not in the "
            f"library yet. Please create them as Custom Instructions/"
            f"Conditions (one file per class, complete file content in a "
            f"single python block):\n{blocks}\n\n"
            f"Use exactly these class names so the planned flow finds "
            f"them directly.")
