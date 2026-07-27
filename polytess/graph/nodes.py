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

from polytess.core.conditions import BranchList, CheckMode, ConditionList
from polytess.core.context import Context
from polytess.core.events import Event
from polytess.core.instructions import InstructionList
from polytess.core.metadata import meta
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


@meta(title="Sub-Workflow", category="Nodes/Sub-Workflow", icon="graph", color="blue",
      description="Runs another workflow file, then continues")
class SubGraphNode(Node):
    PORTS = (
        PortSpec("in", "in", allow_multiple=True, label="In"),
        PortSpec("out", "out", label="Out"),
    )
    accent = "blue"

    def __init__(self):
        super().__init__()
        self.file: str = ""            # path to *.flow.json (relative to workdir)
        self.share_globals: bool = True

    @property
    def default_name(self) -> str:
        import os
        return os.path.basename(self.file) if self.file else "Sub-Workflow"

    async def process(self, ctx: Context, processor) -> None:
        from polytess.graph.model import Graph
        from polytess.graph.processor import GraphProcessor
        if self.file:
            path = ctx.resolve_path(self.file)
            sub_graph = Graph.load(path)
            sub_ctx = Context(graph=sub_graph, globals_scope=ctx.globals,
                              logger=ctx.logger, target=ctx.target,
                              workdir=ctx.workdir)
            sub_processor = GraphProcessor(sub_graph)
            ctx.info(f"Sub-workflow start: {self.file}")
            await sub_processor.run(sub_ctx)
            ctx.info(f"Sub-workflow done: {self.file}")
        if not ctx.is_cancelled:
            await processor.run_children(self, "out", ctx)
