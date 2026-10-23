# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Concrete node types — Start / Exit / Actions / Conditions / Branch /
Trigger / Sub-Workflow.

Execution is push-based: a node runs its
payload, then asks the processor to run its children on the matching
output port. Multiple outgoing edges run concurrently.
"""

from __future__ import annotations

import copy
import os

from polytess.core.conditions import BranchList, CheckMode, ConditionList
from polytess.core.context import Context
from polytess.core.events import Event
from polytess.core.instructions import InstructionList
from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem
from polytess.core.properties import (GetNone, PropertyGetAny, PropertySetAny,
                                      SetNone)
from polytess.core.variables import GlobalScope
from polytess.graph.model import Node, PortSpec


@meta(title="Start", category="Nodes/Start", icon="play", color="purple",
      description="Entry point — runs once when the workflow starts", hidden=True)
class StartNode(Node):
    PORTS = (PortSpec("out", "out", label="Out"),)
    deletable = False
    renamable = False
    accent = "purple"

    def __init__(self):
        super().__init__()
        self.instructions = InstructionList()

    @property
    def counter(self) -> int:
        return len(self.instructions)

    def content_lines(self):
        return list(self.instructions)

    async def process(self, ctx: Context, processor) -> None:
        await self.instructions.run(ctx)
        if not ctx.is_cancelled:
            await processor.run_children(self, "out", ctx)


@meta(title="Exit", category="Nodes/Exit", icon="stop", color="purple",
      description="Runs its actions, then finishes the workflow", hidden=True)
class ExitNode(Node):
    PORTS = (PortSpec("in", "in", allow_multiple=True, label="In"),)
    deletable = False
    renamable = False
    accent = "purple"

    def __init__(self):
        super().__init__()
        self.instructions = InstructionList()

    @property
    def counter(self) -> int:
        return len(self.instructions)

    def content_lines(self):
        return list(self.instructions)

    async def process(self, ctx: Context, processor) -> None:
        await self.instructions.run(ctx)
        processor.notify_exit(ctx)


@meta(title="Actions", category="Nodes/Actions", icon="instructions", color="blue",
      description="Runs a list of actions in order, then continues")
class ActionsNode(Node):
    PORTS = (
        PortSpec("in", "in", allow_multiple=True, label="In"),
        PortSpec("trigger-in", "in", vertical=True, allow_multiple=True, label="In"),
        PortSpec("out", "out", label="Out"),
    )
    accent = "blue"

    def __init__(self):
        super().__init__()
        self.instructions = InstructionList()

    @property
    def counter(self) -> int:
        return len(self.instructions)

    def content_lines(self):
        return list(self.instructions)

    async def process(self, ctx: Context, processor) -> None:
        await self.instructions.run(ctx)
        if not ctx.is_cancelled:
            await processor.run_children(self, "out", ctx)


@meta(title="Conditions", category="Nodes/Conditions", icon="conditions", color="green",
      description="Checks conditions and continues on the Success or Fail port")
class ConditionsNode(Node):
    PORTS = (
        PortSpec("in", "in", allow_multiple=True, label="In"),
        PortSpec("trigger-in", "in", vertical=True, allow_multiple=True, label="In"),
        PortSpec("success", "out", label="Out Success"),
        PortSpec("fail", "out", label="Out Fail"),
    )
    accent = "green"
    FIELD_CHOICES = {"check_mode": ["and", "or"]}

    def __init__(self):
        super().__init__()
        self.conditions = ConditionList()
        self.check_mode: str = "and"

    @property
    def counter(self) -> int:
        return len(self.conditions)

    def content_lines(self):
        return list(self.conditions)

    async def process(self, ctx: Context, processor) -> None:
        result = self.conditions.check(ctx, CheckMode(self.check_mode))
        processor.report_result(self, result)
        await processor.run_children(self, "success" if result else "fail", ctx)


@meta(title="Branch", category="Nodes/Branch", icon="branch", color="green",
      description="If / else-if / else — runs the first matching branch, then continues")
class BranchNode(Node):
    PORTS = (
        PortSpec("in", "in", allow_multiple=True, label="In"),
        PortSpec("trigger-in", "in", vertical=True, allow_multiple=True, label="In"),
        PortSpec("out", "out", label="Out"),
    )
    accent = "green"

    def __init__(self):
        super().__init__()
        self.branches = BranchList()

    @property
    def counter(self) -> int:
        return len(self.branches)

    def content_lines(self):
        return list(self.branches)

    async def process(self, ctx: Context, processor) -> None:
        index = await self.branches.evaluate(ctx)
        processor.report_result(self, index >= 0)
        if not ctx.is_cancelled:
            await processor.run_children(self, "out", ctx)


@meta(title="Trigger", category="Nodes/Trigger", icon="bolt", color="red",
      description="Fires its children whenever its event triggers")
class TriggerNode(Node):
    PORTS = (PortSpec("out", "out", vertical=True, label="Out"),)
    accent = "red"

    def __init__(self):
        super().__init__()
        self.event: Event | None = None

    @property
    def default_name(self) -> str:
        if self.event is not None:
            return self.event.title
        return super().default_name

    @property
    def counter(self) -> int:
        return 1 if self.event is not None else 0

    def content_lines(self):
        return [self.event] if self.event is not None else []

    async def process(self, ctx: Context, processor) -> None:
        # Arm the event; every fire spawns a child run.
        if self.event is None:
            return

        def fire(payload):
            child = ctx.child(target=payload if payload is not None else ctx.target)
            processor.spawn(processor.run_children(self, "out", child))
            processor.pulse(self)

        self.event.start(fire, ctx)
        processor.register_event(self.event)


# --------------------------------------------------------------------------- #
# Sub-Workflow
# --------------------------------------------------------------------------- #

MAX_SUBFLOW_DEPTH = 32


def resolve_subflow_path(file: str, graph_path: str = "", workdir: str = "") -> str:
    """Relative sub-workflow paths resolve against the CALLING flow's folder
    (like the GUI's 'Open Sub-Workflow'); the workdir is the fallback."""
    path = os.path.expandvars(os.path.expanduser(str(file)))
    if os.path.isabs(path):
        return os.path.normpath(path)
    bases = [os.path.dirname(graph_path)] if graph_path else []
    bases.append(workdir or os.getcwd())
    candidates = [os.path.normpath(os.path.join(base, path)) for base in bases]
    return next((c for c in candidates if os.path.isfile(c)), candidates[0])


def has_persistent_triggers(graph) -> bool:
    return any(isinstance(n, TriggerNode) and n.enabled and n.event is not None
               and getattr(n.event, "persistent", False) for n in graph.nodes)


def _isolated_globals(scope: GlobalScope) -> GlobalScope:
    """Snapshot of *scope* — the sub-workflow reads the caller's globals,
    but its writes stay private."""
    from polytess.core.serialization import from_data, to_data
    isolated = GlobalScope()
    isolated.variables = from_data(to_data(scope.variables))
    isolated.lists = from_data(to_data(scope.lists))
    return isolated


@meta(title="Sub-Workflow Input", icon="variable", color="blue", hidden=True)
class SubFlowInput(PolymorphicItem):
    """Passes a value of the calling flow into a graph variable/list of the
    sub-workflow before it starts."""

    FIELD_HELP = {
        "param": "Graph variable or list of the SUB-workflow that receives "
                 "the value (its interface parameter).",
        "value": "Value from the calling flow — constant, variable, list, "
                 "table, template, loop target …; 'None' keeps the "
                 "sub-workflow's own default.",
    }

    def __init__(self, param: str = "", value: PropertyGetAny | None = None):
        super().__init__()
        self.param = param
        self.value = value if value is not None else PropertyGetAny()

    @property
    def is_bound(self) -> bool:
        return self.is_enabled and not isinstance(self.value.source, GetNone)

    @property
    def title(self) -> str:
        return f"in   {self.param or '?'}  ←  {self.value.display}"


@meta(title="Sub-Workflow Output", icon="variable", color="blue", hidden=True)
class SubFlowOutput(PolymorphicItem):
    """Copies a graph variable/list of the sub-workflow back into the
    calling flow after it finished."""

    FIELD_HELP = {
        "param": "Graph variable or list of the SUB-workflow whose final "
                 "value is returned.",
        "target": "Where the calling flow stores the returned value "
                  "(graph/global variable, list or table).",
    }

    def __init__(self, param: str = "", target: PropertySetAny | None = None):
        super().__init__()
        self.param = param
        self.target = target if target is not None else PropertySetAny()

    @property
    def is_bound(self) -> bool:
        return self.is_enabled and not isinstance(self.target.source, SetNone)

    @property
    def title(self) -> str:
        return f"out  {self.param or '?'}  →  {self.target.display}"


def _write_param(graph, name: str, value) -> None:
    lst = graph.lists.get(name)
    if lst is not None:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"input {name!r} is a list in the sub-workflow — "
                            f"got {type(value).__name__}")
        lst.clear()
        for item in value:
            lst.push(item)
        graph.lists.notify(name)
    else:
        graph.variables.set(name, value)


def _read_param(graph, name: str):
    lst = graph.lists.get(name)
    if lst is not None:
        return list(lst.items)
    return graph.variables.get(name)


@meta(title="Sub-Workflow", category="Nodes/Sub-Workflow", icon="graph", color="blue",
      description="Runs another workflow file with explicit inputs/outputs, then continues")
class SubGraphNode(Node):
    """Calls another flow like a function.

    The sub-workflow is loaded fresh for every call, so its graph
    variables are private to that call (parallel calls cannot interfere).
    Data flows only through the declared bindings: *inputs* are evaluated
    in the caller and written into the sub-workflow's graph variables
    before it starts, *outputs* are copied back after it finished."""

    PORTS = (
        PortSpec("in", "in", allow_multiple=True, label="In"),
        PortSpec("out", "out", label="Out"),
    )
    accent = "blue"

    FIELD_HELP = {
        "file": "Workflow file (*.flow.json); relative paths resolve against "
                "the calling flow's folder, then the working directory.",
        "share_globals": "On: the sub-workflow reads and writes the caller's "
                         "global variables. Off: it works on a private copy "
                         "— global writes do not leak back.",
        "fail_on_error": "On: a failed node inside the sub-workflow fails "
                         "this node (the chain stops, outputs are not "
                         "returned). Off: only a warning is logged.",
    }

    def __init__(self):
        super().__init__()
        self.file: str = ""
        self.inputs: list[SubFlowInput] = []
        self.outputs: list[SubFlowOutput] = []
        self.share_globals: bool = True
        self.fail_on_error: bool = True

    @property
    def default_name(self) -> str:
        return os.path.basename(self.file) if self.file else "Sub-Workflow"

    @property
    def counter(self) -> int:
        return len(self.inputs) + len(self.outputs)

    def content_lines(self):
        return list(self.inputs) + list(self.outputs)

    def resolve_file(self, graph_path: str = "", workdir: str = "") -> str:
        return resolve_subflow_path(self.file, graph_path, workdir)

    def binding_problems(self, sub_graph) -> list[str]:
        """Bindings that name no graph variable/list of *sub_graph*."""
        known = set(sub_graph.variables.names()) | set(sub_graph.lists.names())
        problems = []
        for kind, bindings in (("input", self.inputs), ("output", self.outputs)):
            for binding in bindings:
                if not binding.is_enabled:
                    continue
                if not binding.param:
                    problems.append(f"{kind} binding without a sub-workflow "
                                    f"variable name")
                elif binding.param not in known:
                    problems.append(f"{kind} {binding.param!r}: no graph "
                                    f"variable/list of that name in "
                                    f"{os.path.basename(self.file)}")
        return problems

    async def process(self, ctx: Context, processor) -> None:
        if self.file:
            await self._call(ctx)
        if not ctx.is_cancelled:
            await processor.run_children(self, "out", ctx)

    async def _call(self, ctx: Context) -> None:
        from polytess.graph.model import Graph
        from polytess.graph.processor import GraphProcessor

        path = self.resolve_file(getattr(ctx.graph, "path", "") or "", ctx.workdir)
        if len(ctx.call_stack) >= MAX_SUBFLOW_DEPTH:
            chain = " → ".join(os.path.basename(p) for p in ctx.call_stack)
            raise RecursionError(f"sub-workflows nested deeper than "
                                 f"{MAX_SUBFLOW_DEPTH} levels: {chain}")
        sub_graph = Graph.load(path)
        problems = self.binding_problems(sub_graph)
        if problems:
            raise ValueError("; ".join(problems))

        for binding in self.inputs:
            if binding.is_bound:
                _write_param(sub_graph, binding.param,
                             copy.deepcopy(binding.value.get(ctx)))

        sub_ctx = Context(graph=sub_graph,
                          globals_scope=ctx.globals if self.share_globals
                          else _isolated_globals(ctx.globals),
                          logger=ctx.logger, target=ctx.target,
                          workdir=ctx.workdir)
        sub_ctx._parent = ctx
        sub_ctx.call_stack = ctx.call_stack + (path,)
        if has_persistent_triggers(sub_graph):
            ctx.warning(f"Sub-workflow {self.file} has persistent triggers — "
                        f"it only returns when one of its Exit nodes runs")

        sub_processor = GraphProcessor(sub_graph)
        ctx.info(f"Sub-workflow start: {self.file}")
        await sub_processor.run(sub_ctx)
        if ctx.is_cancelled:
            return
        if sub_processor.failed_nodes:
            message = (f"sub-workflow {self.file}: failed node(s) "
                       f"{', '.join(sub_processor.failed_nodes)}")
            if self.fail_on_error:
                raise RuntimeError(message)
            ctx.warning(message)

        for binding in self.outputs:
            if binding.is_bound:
                binding.target.set(_read_param(sub_graph, binding.param), ctx)
        ctx.info(f"Sub-workflow done: {self.file}")
