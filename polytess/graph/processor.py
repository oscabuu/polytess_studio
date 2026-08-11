# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""GraphProcessor — asynchronous, push-based graph execution.

Push-based execution: only Start and Trigger nodes are entry points.
Each node runs its payload, then schedules its children; several outgoing
edges fan out concurrently (asyncio). There is no global compute order.

Per-node status (idle/running/success/fail) is reported through the
``on_status`` callback so the GUI can live-highlight nodes.
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Callable

from polytess.core.context import Context
from polytess.core.events import Event
from polytess.graph.model import Graph, Node


class NodeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAIL = "fail"
    PAUSED = "paused"


StatusFn = Callable[[Node, NodeStatus], None]


class GraphProcessor:

    def __init__(self, graph: Graph, on_status: StatusFn | None = None):
        self.graph = graph
        self.on_status: list[StatusFn] = [on_status] if on_status else []
        self.on_state: list[Callable[[str], None]] = []   # "running" | "paused"
        self._tasks: set[asyncio.Task] = set()
        self._events: list[Event] = []
        self._exit = asyncio.Event()
        self._stopped = False
        self._results: dict[str, bool] = {}      # ConditionsNode outcomes
        self.is_running = False
        self._paused = False
        self._step_tokens = 0

    # ---- pause / step / breakpoints ----------------------------------------- #

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        if not self._paused:
            self._paused = True
            self._emit_state()

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self._step_tokens = 0
            self._emit_state()

    def step(self) -> None:
        """Let exactly one waiting node proceed, then stay paused."""
        if not self._paused:
            self.pause()
        self._step_tokens += 1

    def _emit_state(self) -> None:
        state = "paused" if self._paused else "running"
        for fn in list(self.on_state):
            fn(state)

    async def _gate(self, node: Node, ctx: Context) -> None:
        """Blocks node execution while paused; auto-pauses on breakpoints."""
        if node.breakpoint:
            if not self._paused:
                self.pause()
            ctx.info(f"Breakpoint reached: {node.name}")
        if not self._paused:
            return
        self._emit(node, NodeStatus.PAUSED)
        while self._paused and self._step_tokens <= 0:
            if self._stopped or ctx.is_cancelled:
                return
            await asyncio.sleep(0.05)
        if self._paused and self._step_tokens > 0:
            self._step_tokens -= 1
            ctx.info(f"Step: {node.name}")

    # ---- status reporting -------------------------------------------------- #

    def _emit(self, node: Node, status: NodeStatus) -> None:
        for fn in list(self.on_status):
            fn(node, status)

    def report_result(self, node: Node, result: bool) -> None:
        self._results[node.guid] = result

    def pulse(self, node: Node) -> None:
        """Short visual blip for trigger nodes."""
        self._emit(node, NodeStatus.RUNNING)
        self._emit(node, NodeStatus.SUCCESS)

    # ---- task management ----------------------------------------------------- #

    def spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def register_event(self, event: Event) -> None:
        self._events.append(event)

    def notify_exit(self, ctx: Context) -> None:
        """Called by ExitNode — ends the whole run."""
        self._exit.set()

    # ---- node execution --------------------------------------------------------- #

    async def process_node(self, node: Node, ctx: Context) -> None:
        if self._stopped or ctx.is_cancelled or not node.enabled:
            return
        await self._gate(node, ctx)
        if self._stopped or ctx.is_cancelled:
            self._emit(node, NodeStatus.IDLE)
            return
        self._results.pop(node.guid, None)
        self._emit(node, NodeStatus.RUNNING)
        try:
            await node.process(ctx, self)
        except asyncio.CancelledError:
            self._emit(node, NodeStatus.IDLE)
            raise
        except Exception as exc:
            ctx.error(f"Node '{node.name}': {exc.__class__.__name__}: {exc}")
            self._emit(node, NodeStatus.FAIL)
            return
        result = self._results.get(node.guid, True)
        self._emit(node, NodeStatus.SUCCESS if result else NodeStatus.FAIL)

    async def run_children(self, node: Node, port: str, ctx: Context) -> None:
        children = self.graph.children(node, port)
        if not children:
            return
        if len(children) == 1:
            await self.process_node(children[0], ctx)
            return
        await asyncio.gather(*(self.process_node(c, ctx) for c in children))

    # ---- lifecycle ------------------------------------------------------------------ #

    async def run(self, ctx: Context) -> None:
        """Start all entry points; return when the flow is done.

        The run finishes when (a) an Exit node executed, or (b) all initial
        flows completed and no persistent trigger events are armed.
        """
        from polytess.graph.nodes import StartNode, TriggerNode
        self.is_running = True
        self._stopped = False
        self._exit = asyncio.Event()
        ctx.runner = self
        try:
            # Arm every trigger FIRST and completely (their process() only
            # registers the event and returns) — otherwise a start chain
            # of non-yielding instructions can change a variable before
            # On Variable Changed is even listening, and the trigger
            # silently never fires.
            for node in self.graph.nodes:
                if isinstance(node, TriggerNode) and node.enabled:
                    await self.process_node(node, ctx)
            for node in self.graph.nodes:
                if isinstance(node, StartNode) and node.enabled:
                    self.spawn(self.process_node(node, ctx))

            exit_wait = asyncio.ensure_future(self._exit.wait())
            try:
                # Drain the *dynamic* task set: trigger events may spawn new
                # tasks at any time. Stop early when an Exit node fired.
                while not self._exit.is_set():
                    live = set(self._tasks)
                    if not live:
                        # no running work — stay alive only for persistent
                        # trigger events (On Signal / On Timer / On File Changed)
                        if any(e.persistent for e in self._events) and not self._stopped:
                            await exit_wait
                        break
                    await asyncio.wait(live | {exit_wait},
                                       return_when=asyncio.FIRST_COMPLETED)
            finally:
                if not exit_wait.done():
                    exit_wait.cancel()
        finally:
            await self._shutdown()
            for node in self.graph.nodes:
                self._emit(node, NodeStatus.IDLE)
            self.is_running = False

    def stop(self) -> None:
        """Abort the run (GUI Stop button / Ctrl+C)."""
        self._stopped = True
        self._exit.set()
        for task in list(self._tasks):
            task.cancel()

    async def _shutdown(self) -> None:
        for event in self._events:
            try:
                event.stop()
            except Exception:
                pass
        self._events.clear()
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
