"""Phase-2 tests: graph model, connection rules, push-based processor."""

import asyncio

import pytest

from polytess.core import Context, GlobalScope, Instruction, InstructionList, meta
from polytess.core.conditions import Condition, ConditionList
from polytess.core.events import Event
from polytess.graph import (
    ActionsNode, ConditionsNode, ExitNode, Graph, GraphProcessor, NodeStatus,
    StartNode, TriggerNode,
)


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


@meta(title="Test Push", category="Testing/Push", hidden=True)
class TestingPush(Instruction):
    def __init__(self, tag: str = ""):
        super().__init__()
        self.tag = tag

    async def run(self, ctx):
        lst = ctx.graph_lists.require("trace")
        lst.push(self.tag)


@meta(title="Test Flag", category="Testing/Flag", hidden=True)
class TestingFlag(Condition):
    def __init__(self, expected: bool = True):
        super().__init__()
        self.expected = expected

    def run(self, ctx):
        return bool(ctx.graph_variables.get("flag")) == self.expected


def build_graph() -> Graph:
    graph = Graph("test")
    graph.ensure_endpoints()
    return graph


def ctx_for(graph) -> Context:
    return Context(graph=graph, logger=lambda lvl, msg: None)


def trace(graph) -> list:
    lst = graph.lists.get("trace")
    return lst.items if lst else []


async def test_linear_flow_start_actions_exit():
    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    exit_node = next(iter(graph.nodes_of_type(ExitNode)))
    a = graph.add_node(ActionsNode())
    a.instructions.instructions.append(TestingPush("A"))
    exit_node.instructions.instructions.append(TestingPush("exit"))

    assert graph.connect(start, "out", a, "in") is not None
    assert graph.connect(a, "out", exit_node, "in") is not None

    await GraphProcessor(graph).run(ctx_for(graph))
    assert trace(graph) == ["A", "exit"]


async def test_conditions_route_success_fail():
    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    cond = graph.add_node(ConditionsNode())
    cond.conditions.conditions.append(TestingFlag(True))
    ok = graph.add_node(ActionsNode())
    ok.instructions.instructions.append(TestingPush("ok"))
    fail = graph.add_node(ActionsNode())
    fail.instructions.instructions.append(TestingPush("fail"))
    graph.connect(start, "out", cond, "in")
    graph.connect(cond, "success", ok, "in")
    graph.connect(cond, "fail", fail, "in")

    graph.variables.set("flag", True)
    statuses: list[tuple[str, NodeStatus]] = []
    processor = GraphProcessor(graph, on_status=lambda n, s: statuses.append((n.name, s)))
    await processor.run(ctx_for(graph))
    assert trace(graph) == ["ok"]
    assert ("Conditions", NodeStatus.SUCCESS) in statuses

    graph.lists.get("trace").clear()
    graph.variables.set("flag", False)
    await GraphProcessor(graph).run(ctx_for(graph))
    assert trace(graph) == ["fail"]


async def test_parallel_fanout():
    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    a, b = graph.add_node(ActionsNode()), graph.add_node(ActionsNode())
    a.instructions.instructions.append(TestingPush("a"))
    b.instructions.instructions.append(TestingPush("b"))
    graph.connect(start, "out", a, "in")
    graph.connect(start, "out", b, "in")
    await GraphProcessor(graph).run(ctx_for(graph))
    assert sorted(trace(graph)) == ["a", "b"]


async def test_input_port_single_connection_rule():
    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    a = graph.add_node(ActionsNode())
    b = graph.add_node(ActionsNode())
    graph.connect(start, "out", a, "in")
    graph.connect(start, "out", b, "in")
    # 'out' allows multiple, both edges live
    assert len(graph.out_edges(start)) == 2
    # reconnecting the same pair does not duplicate
    graph.connect(start, "out", a, "in")
    assert len(graph.out_edges(start)) == 2
    # self connection rejected
    assert graph.connect(a, "out", a, "in") is None


@meta(title="Test Once", category="Testing/Once", hidden=True)
class TestingOnceEvent(Event):
    persistent = False

    def start(self, fire, ctx):
        super().start(fire, ctx)
        self.fire("payload-1")


async def test_trigger_node_fires_children():
    graph = build_graph()
    trigger = graph.add_node(TriggerNode())
    trigger.event = TestingOnceEvent()
    a = graph.add_node(ActionsNode())
    a.instructions.instructions.append(TestingPush("fired"))
    graph.connect(trigger, "out", a, "trigger-in")
    await GraphProcessor(graph).run(ctx_for(graph))
    assert trace(graph) == ["fired"]


async def test_stop_cancels_everything():
    @meta(title="Test Forever", category="Testing/Forever", hidden=True)
    class TestingForever(Instruction):
        async def run(self, ctx):
            await self.wait_seconds(ctx, 60)

    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    slow = graph.add_node(ActionsNode())
    slow.instructions.instructions.append(TestingForever())
    slow.instructions.instructions.append(TestingPush("never"))
    graph.connect(start, "out", slow, "in")

    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.1)
    ctx.cancel()
    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert trace(graph) == []


async def test_on_variable_changed_fires_on_real_change():
    from polytess.library.events.event_on_variable_changed import OnVariableChanged

    graph = build_graph()
    graph.variables.declare("counter", "number", 0)
    trigger = graph.add_node(TriggerNode())
    trigger.event = OnVariableChanged("counter")
    a = graph.add_node(ActionsNode())
    a.instructions.instructions.append(TestingPush("changed"))
    graph.connect(trigger, "out", a, "trigger-in")

    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.05)

    graph.variables.set("counter", 1)      # real change -> fires
    await asyncio.sleep(0.05)
    graph.variables.set("counter", 1)      # identical value -> filtered
    await asyncio.sleep(0.05)
    graph.variables.set("unrelated", 9)    # other variable -> filtered
    await asyncio.sleep(0.05)

    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert trace(graph) == ["changed"]


async def test_on_variable_changed_any_and_list():
    from polytess.core.properties import GetGraphList, GetTarget
    from polytess.library.events.event_on_variable_changed import OnVariableChanged
    from polytess.library.instructions.instruction_add_to_list import AddToList

    graph = build_graph()
    graph.variables.declare("alpha", "string", "x")
    graph.lists.declare("watched", "string", ["a"])

    # any-variable trigger: payload (= Loop Target) is the changed name
    any_trigger = graph.add_node(TriggerNode())
    any_trigger.event = OnVariableChanged()
    a = graph.add_node(ActionsNode())
    collect = AddToList("hits")
    collect.value.source = GetTarget()
    a.instructions.instructions.append(collect)
    graph.connect(any_trigger, "out", a, "trigger-in")

    # list trigger: fires on notify with the new items as payload
    list_trigger = graph.add_node(TriggerNode())
    list_trigger.event = OnVariableChanged()
    list_trigger.event.variable.source = GetGraphList("watched")
    b = graph.add_node(ActionsNode())
    b.instructions.instructions.append(TestingPush("list-changed"))
    graph.connect(list_trigger, "out", b, "trigger-in")

    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.05)

    graph.variables.set("alpha", "y")
    await asyncio.sleep(0.05)
    lst = graph.lists.get("watched")
    lst.push("b")
    graph.lists.notify("watched")
    await asyncio.sleep(0.05)

    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert graph.lists.get("hits").items == ["alpha"]
    assert "list-changed" in trace(graph)


async def test_graph_save_load_roundtrip(tmp_path):
    graph = build_graph()
    start = next(iter(graph.nodes_of_type(StartNode)))
    a = graph.add_node(ActionsNode())
    a.custom_name = "Prepare"
    a.x, a.y = 100, 50
    a.instructions.instructions.append(TestingPush("A"))
    graph.connect(start, "out", a, "in")
    graph.variables.declare("count", "number", 3)
    graph.lists.declare("files", "string", ["a.txt"])

    path = str(tmp_path / "wf.flow.json")
    graph.save(path)
    clone = Graph.load(path)
    assert clone.name == "test"
    assert clone.variables.get("count") == 3.0
    assert clone.lists.get("files").items == ["a.txt"]
    node = clone.node_by_guid(a.guid)
    assert node is not None and node.custom_name == "Prepare" and node.x == 100
    assert len(clone.edges) == 1

    await GraphProcessor(clone).run(ctx_for(clone))
    assert trace(clone) == ["A"]
