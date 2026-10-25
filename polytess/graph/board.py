# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Kanban board projection of a main process (PLAN_VIEWER.md, section 8).

A *main process* is an ordinary flow whose Sub-Workflow nodes are the
**cards**; the flow's edges are the **dependencies**. This module has no
Qt: it derives the board (``board_spec``), keeps the persisted run
state next to the flow (``BoardState``) and runs single cards outside
the main flow's processor (``BoardRunner``) — exactly what
``SubGraphNode.call`` does inside a run, but driven by the user.

Card status: ``pending`` (never run / no result), ``queued`` (waits for
predecessors in a planned run), ``active``, ``done``, ``failed``,
``stale`` (done, but its inputs or a predecessor changed since).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from polytess.core.context import Context
from polytess.graph.model import Graph
from polytess.graph.nodes import (BranchNode, ConditionsNode, ExitNode,
                                  StartNode, SubGraphNode, TriggerNode)

PENDING, QUEUED, ACTIVE, DONE, FAILED, STALE = (
    "pending", "queued", "active", "done", "failed", "stale")


class BoardError(Exception):
    pass


# ---- projection ------------------------------------------------------------------- #

@dataclass
class Card:
    guid: str
    title: str
    file: str
    description: str = ""
    predecessors: list[str] = field(default_factory=list)   # direct, card guids
    conditional: bool = False      # a Conditions/Branch node sits before it
    level: int = 0                 # longest predecessor chain (column hint)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class BoardSpec:
    flow_name: str
    cards: list[Card] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)   # cycles, missing files

    def card(self, guid: str) -> Card | None:
        return next((c for c in self.cards if c.guid == guid), None)

    def card_by_title(self, title: str) -> Card | None:
        return next((c for c in self.cards if c.title == title), None)

    def successors(self, guid: str) -> list[Card]:
        return [c for c in self.cards if guid in c.predecessors]

    def ancestors(self, guid: str) -> list[str]:
        """All transitive predecessors, dependency order (roots first)."""
        seen: list[str] = []

        def walk(g: str) -> None:
            for pred in (self.card(g).predecessors if self.card(g) else []):
                if pred not in seen:
                    walk(pred)
                    seen.append(pred)
        walk(guid)
        return seen

    def to_dict(self) -> dict:
        return {"flow": self.flow_name, "cards": [c.to_dict() for c in self.cards],
                "problems": list(self.problems)}


def board_spec(graph: Graph) -> BoardSpec:
    """Cards = enabled Sub-Workflow nodes; a dependency A → B exists when
    B is reachable from A through non-card nodes (Actions, Conditions,
    Branch, Trigger …). Passing a Conditions/Branch node marks B as
    conditional. Cycles between cards are reported as problems."""
    spec = BoardSpec(flow_name=graph.name)
    cards = {n.guid: n for n in graph.nodes
             if isinstance(n, SubGraphNode) and n.enabled}
    for node in cards.values():
        spec.cards.append(Card(guid=node.guid, title=node.name, file=node.file,
                               description=getattr(node, "description", "")))
    preds: dict[str, set[str]] = {g: set() for g in cards}
    conditional: set[str] = set()

    for start_guid, start in cards.items():
        # walk forward through non-card nodes
        stack = [(child, False) for child in graph.children(start)]
        visited: set[str] = set()
        while stack:
            node, cond = stack.pop()
            if node.guid in visited:
                continue
            visited.add(node.guid)
            if node.guid in cards:
                preds[node.guid].add(start_guid)
                if cond:
                    conditional.add(node.guid)
                continue
            if isinstance(node, ExitNode):
                continue
            passes_condition = cond or isinstance(node, (ConditionsNode, BranchNode))
            for child in graph.children(node):
                stack.append((child, passes_condition))

    for card in spec.cards:
        card.predecessors = sorted(preds[card.guid],
                                   key=lambda g: cards[g].name)
        card.conditional = card.guid in conditional

    # levels + cycle detection (Kahn)
    remaining = {c.guid: set(c.predecessors) for c in spec.cards}
    level = 0
    while remaining:
        ready = [g for g, p in remaining.items() if not p]
        if not ready:
            names = ", ".join(sorted(cards[g].name for g in remaining))
            spec.problems.append(f"dependency cycle between cards: {names}")
            break
        for g in ready:
            spec.card(g).level = level
            del remaining[g]
        for p in remaining.values():
            p.difference_update(ready)
        level += 1
    spec.cards.sort(key=lambda c: (c.level, c.title))
    for card in spec.cards:
        if not card.file:
            spec.problems.append(f"card {card.title!r}: no workflow file set")
    return spec


# ---- persisted run state -------------------------------------------------------- #

def state_path(flow_path: str) -> str:
    base = flow_path[:-len(".flow.json")] if flow_path.endswith(".flow.json") \
        else os.path.splitext(flow_path)[0]
    return base + ".board.json"


@dataclass
class CardState:
    status: str = PENDING
    started: float | None = None
    finished: float | None = None
    duration: float | None = None
    input_hash: str = ""
    log: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class BoardState:
    """``<flow>.board.json``: per-card status + the main flow's variable
    values after the last card, plus a run history for statistics."""

    def __init__(self, path: str = ""):
        self.path = path
        self.cards: dict[str, CardState] = {}
        self.variables: dict = {}          # name -> value (main flow)
        self.lists: dict = {}              # name -> items
        self.history: list[dict] = []      # {card, title, status, started, duration}
        self.auto_advance = True

    # -- io --
    @classmethod
    def load(cls, path: str) -> "BoardState":
        state = cls(path)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for guid, item in (data.get("cards") or {}).items():
                state.cards[guid] = CardState(**{k: v for k, v in item.items()
                                                 if k in CardState().__dict__})
            state.variables = dict(data.get("variables") or {})
            state.lists = dict(data.get("lists") or {})
            state.history = list(data.get("history") or [])
            state.auto_advance = bool(data.get("auto_advance", True))
        return state

    def save(self) -> None:
        if not self.path:
            return
        data = {"cards": {g: c.to_dict() for g, c in self.cards.items()},
                "variables": self.variables, "lists": self.lists,
                "history": self.history[-500:],
                "auto_advance": self.auto_advance}
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False, default=str)

    def card(self, guid: str) -> CardState:
        return self.cards.setdefault(guid, CardState())

    def status(self, guid: str) -> str:
        return self.cards[guid].status if guid in self.cards else PENDING

    # -- main-flow variable snapshot --
    def capture(self, graph: Graph) -> None:
        self.variables = {v.name: v.value.get() for v in graph.variables}
        self.lists = {l.name: list(l.items) for l in graph.lists}

    def restore(self, graph: Graph) -> None:
        for name, value in self.variables.items():
            var = graph.variables.variable(name)
            if var is not None:
                try:
                    var.value.set(value)
                except (TypeError, ValueError):
                    pass
        for name, items in self.lists.items():
            lst = graph.lists.get(name)
            if lst is not None:
                lst.clear()
                for item in items:
                    lst.push(item)

    # -- statistics --
    def summary(self, spec: BoardSpec) -> dict:
        counts = {s: 0 for s in (PENDING, QUEUED, ACTIVE, DONE, FAILED, STALE)}
        for card in spec.cards:
            counts[self.status(card.guid)] += 1
        durations = [h["duration"] for h in self.history
                     if h.get("status") == DONE and h.get("duration")]
        failures: dict[str, int] = {}
        for h in self.history:
            if h.get("status") == FAILED:
                failures[h.get("title", "?")] = failures.get(h.get("title", "?"), 0) + 1
        runs = len(self.history)
        done_runs = sum(1 for h in self.history if h.get("status") == DONE)
        # remaining-time estimate: last known duration per pending card
        last_duration: dict[str, float] = {}
        for h in self.history:
            if h.get("status") == DONE and h.get("duration"):
                last_duration[h["card"]] = h["duration"]
        remaining = [c for c in spec.cards
                     if self.status(c.guid) in (PENDING, QUEUED, STALE, FAILED)]
        known = [last_duration[c.guid] for c in remaining if c.guid in last_duration]
        estimate = (sum(known) + (len(remaining) - len(known))
                    * (sum(known) / len(known) if known else 0.0)) if remaining else 0.0
        return {
            "total": len(spec.cards), "counts": counts,
            "progress": (counts[DONE] / len(spec.cards)) if spec.cards else 0.0,
            "runs": runs, "success_rate": (done_runs / runs) if runs else None,
            "time_spent": sum(durations),
            "estimated_remaining": estimate,
            "most_failing": max(failures, key=failures.get) if failures else None,
        }


# ---- running cards ----------------------------------------------------------------- #

def input_hash(node: SubGraphNode, ctx: Context) -> str:
    """Hash of the card's effective inputs (evaluated bindings + file),
    so a Done card is recognized as still valid when nothing changed."""
    values = {}
    for binding in node.inputs:
        if binding.is_bound:
            try:
                values[binding.param] = binding.value.get(ctx)
            except Exception as exc:
                values[binding.param] = f"<error {exc}>"
    payload = json.dumps({"file": node.file, "inputs": values},
                         sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


class BoardRunner:
    """Runs cards of a main process one by one, keeping ``BoardState``
    current. ``on_change(guid, status)`` fires on every transition,
    ``on_progress(guid, node, NodeStatus)`` on the sub-flow's progress."""

    def __init__(self, graph: Graph, state: BoardState | None = None,
                 workdir: str = "", logger=None,
                 on_change: Callable[[str, str], None] | None = None,
                 on_progress=None, on_log=None):
        self.graph = graph
        self.spec = board_spec(graph)
        self.on_log = on_log            # (guid, level, text) per card run
        self.state = state or BoardState.load(state_path(graph.path)
                                              if graph.path else "")
        self.workdir = workdir or (os.path.dirname(graph.path)
                                   if graph.path else os.getcwd())
        self.logger = logger
        self.on_change = on_change
        self.on_progress = on_progress
        self._running: dict[str, asyncio.Task] = {}
        self.state.restore(graph)
        self.refresh_stale()

    # -- queries --
    def _ctx(self) -> Context:
        return Context(graph=self.graph, workdir=self.workdir, logger=self.logger)

    def node(self, guid: str) -> SubGraphNode:
        node = self.graph.node_by_guid(guid)
        if not isinstance(node, SubGraphNode):
            raise BoardError(f"no card {guid!r}")
        return node

    def status(self, guid: str) -> str:
        return self.state.status(guid)

    def unfinished_predecessors(self, guid: str) -> list[Card]:
        """Transitive predecessors that are not Done, dependency order."""
        return [self.spec.card(g) for g in self.spec.ancestors(guid)
                if self.status(g) != DONE]

    def ready_cards(self) -> list[Card]:
        """Cards whose predecessors are all Done and that are not Done
        or running themselves — what auto-advance would start next."""
        return [c for c in self.spec.cards
                if self.status(c.guid) in (PENDING, STALE, FAILED)
                and all(self.status(p) == DONE for p in c.predecessors)]

    def refresh_stale(self) -> None:
        """Done cards whose inputs changed (hash) or whose predecessor is
        no longer Done become Stale — and so do their successors."""
        ctx = self._ctx()
        changed = True
        while changed:
            changed = False
            for card in self.spec.cards:
                cs = self.state.card(card.guid)
                if cs.status != DONE:
                    continue
                node = self.node(card.guid)
                if cs.input_hash and cs.input_hash != input_hash(node, ctx) \
                        or any(self.status(p) != DONE for p in card.predecessors):
                    cs.status = STALE
                    self._emit(card.guid, STALE)
                    changed = True

    # -- planning --
    def plan(self, guid: str) -> list[Card]:
        """Cards to run, in order, so that *guid* can run with all its
        predecessors Done: unfinished ancestors first, then the card."""
        return self.unfinished_predecessors(guid) + [self.spec.card(guid)]

    # -- running --
    async def run_card(self, guid: str) -> str:
        """Run one card now (predecessors are NOT checked — the caller
        decides, see plan()). Returns the final status."""
        node = self.node(guid)
        card = self.spec.card(guid)
        cs = self.state.card(guid)
        ctx = self._ctx()
        cs.status, cs.started, cs.finished, cs.error = ACTIVE, time.time(), None, ""
        cs.input_hash = input_hash(node, ctx)
        cs.log = self._log_path(card)
        self.state.save()
        self._emit(guid, ACTIVE)
        lines: list[str] = []

        def log(level: str, text: str) -> None:
            lines.append(f"{time.strftime('%H:%M:%S')} [{level}] {text}")
            if self.logger:
                self.logger(level, text)
            if self.on_log:
                self.on_log(guid, level, text)
        ctx.logger = log

        def progress(sub_node, status):
            if self.on_progress:
                self.on_progress(guid, sub_node, status)

        try:
            await node.call(ctx, on_status=progress)
            cs.status = DONE
        except asyncio.CancelledError:
            cs.status, cs.error = PENDING, "cancelled"
            raise
        except Exception as exc:
            cs.status, cs.error = FAILED, f"{exc.__class__.__name__}: {exc}"
            log("error", cs.error)
        finally:
            cs.finished = time.time()
            cs.duration = cs.finished - (cs.started or cs.finished)
            self._write_log(cs.log, lines)
            self.state.capture(self.graph)
            self.state.history.append({"card": guid, "title": card.title,
                                       "status": cs.status, "started": cs.started,
                                       "duration": cs.duration})
            self.state.save()
            self._emit(guid, cs.status)
        if cs.status == DONE:
            self.refresh_stale()
        return cs.status

    async def run_plan(self, guid: str, auto_advance: bool | None = None) -> list[str]:
        """Run *guid* after its unfinished predecessors (in order); with
        auto-advance, keep starting ready successors until nothing is
        ready. Returns the guids run. Stops at the first failure."""
        auto = self.state.auto_advance if auto_advance is None else auto_advance
        done: list[str] = []
        queue = self.plan(guid)
        for card in queue:
            self.state.card(card.guid).status = QUEUED
            self._emit(card.guid, QUEUED)
        while queue:
            card = queue.pop(0)
            status = await self.run_card(card.guid)
            done.append(card.guid)
            if status != DONE:
                for rest in queue:            # un-queue the remainder
                    if self.status(rest.guid) == QUEUED:
                        self.state.card(rest.guid).status = PENDING
                        self._emit(rest.guid, PENDING)
                break
            if auto and not queue:
                queue = [c for c in self.ready_cards() if c.guid not in done]
        self.state.save()
        return done

    async def run_all(self) -> list[str]:
        """Run every card in dependency order (stops at the first failure)."""
        done: list[str] = []
        while True:
            ready = [c for c in self.ready_cards() if c.guid not in done]
            if not ready:
                break
            status = await self.run_card(ready[0].guid)
            done.append(ready[0].guid)
            if status != DONE:
                break
        return done

    def reset(self, guid: str | None = None) -> None:
        """Forget results — one card (and its successors) or everything."""
        targets = list(self.state.cards) if guid is None else [guid] + [
            c.guid for c in self.spec.cards if guid in self.spec.ancestors(c.guid)]
        for g in targets:
            if g in self.state.cards:
                self.state.cards[g] = CardState()
                self._emit(g, PENDING)
        self.state.save()

    # -- helpers --
    def _emit(self, guid: str, status: str) -> None:
        if self.on_change:
            self.on_change(guid, status)

    def _log_path(self, card: Card) -> str:
        folder = os.path.join(self.workdir, ".runs")
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in card.title)
        return os.path.join(folder, f"{safe}_{time.strftime('%Y%m%d_%H%M%S')}.log")

    @staticmethod
    def _write_log(path: str, lines: list[str]) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        except OSError:
            pass
