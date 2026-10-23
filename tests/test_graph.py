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


async def test_trigger_armed_before_start_chain_runs():
    """Regression: a start chain of non-yielding instructions used to
    finish before triggers were armed — On Variable Changed silently
    missed changes made by the flow itself (the sectioning pattern:
    SetBool section_1_completed -> trigger starts section 2)."""
    from polytess.core.properties import PropertySetBool, SetGraphVariable
    from polytess.library.events.event_on_variable_changed import \
        OnVariableChanged
    from polytess.library.instructions.instruction_set_bool import SetBool

    graph = build_graph()
    graph.variables.declare("section_1_completed", "bool", False)
    start = next(iter(graph.nodes_of_type(StartNode)))
    section1 = graph.add_node(ActionsNode())
    section1.instructions.instructions.append(
        SetBool(PropertySetBool(SetGraphVariable("section_1_completed")),
                True))
    graph.connect(start, "out", section1, "in")

    trigger = graph.add_node(TriggerNode())
    trigger.event = OnVariableChanged("section_1_completed")
    section2 = graph.add_node(ActionsNode())
    section2.instructions.instructions.append(TestingPush("section 2 ran"))
    graph.connect(trigger, "out", section2, "trigger-in")

    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.1)
    processor.stop()
    await asyncio.wait_for(task, timeout=2.0)
    assert trace(graph) == ["section 2 ran"]


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


# ---- sub-workflow bindings ------------------------------------------------- #

@pytest.fixture(autouse=True)
def _fresh_global_scope():
    """Sub-workflow tests assert on global variables — start every test
    with an empty singleton instead of depending on test order."""
    GlobalScope.reset()
    yield
    GlobalScope.reset()


from polytess.core.properties import (GetGraphList, GetGraphVariable,  # noqa: E402
                                      PropertyGetAny, PropertySetAny,
                                      SetGlobalVariable, SetGraphList,
                                      SetGraphVariable)
from polytess.graph import SubFlowInput, SubFlowOutput, SubGraphNode  # noqa: E402


@meta(title="Test Double", category="Testing/Double", hidden=True)
class TestingDouble(Instruction):
    """y = 2 * x (yields in between, so parallel calls interleave)."""

    async def run(self, ctx):
        x = ctx.graph_variables.get("x")
        await asyncio.sleep(0.01)
        ctx.graph_variables.set("y", 2 * x)
        ctx.graph_lists.require("items").push("child")
        ctx.globals.variables.set("touched", "yes")


@meta(title="Test Raise", category="Testing/Raise", hidden=True)
class TestingRaise(Instruction):
    async def run(self, ctx):
        raise RuntimeError("boom")


def _linear(graph, *nodes):
    previous = next(iter(graph.nodes_of_type(StartNode)))
    for node in nodes:
        graph.add_node(node)
        graph.connect(previous, "out", node, "in")
        previous = node
    return nodes


def _child_flow(path, *instructions):
    child = build_graph()
    child.variables.declare("x", "number", 1)
    child.variables.declare("y", "number", 0)
    child.lists.declare("items", "string", [])
    actions = ActionsNode()
    actions.instructions.instructions.extend(instructions)
    _linear(child, actions)
    child.save(str(path))


def _sub_node(file, **bindings):
    node = SubGraphNode()
    node.file = file
    node.inputs.append(SubFlowInput("x", PropertyGetAny(GetGraphVariable(bindings.get("x", "a")))))
    node.outputs.append(SubFlowOutput("y", PropertySetAny(SetGraphVariable(bindings.get("y", "res")))))
    return node


def _parent(tmp_path, *nodes):
    graph = build_graph()
    graph.variables.declare("a", "number", 5)
    graph.variables.declare("b", "number", 7)
    graph.variables.declare("res", "number", 0)
    graph.variables.declare("res2", "number", 0)
    _linear(graph, *nodes)
    path = str(tmp_path / "parent.flow.json")
    graph.save(path)
    return Graph.load(path)


async def test_subflow_passes_inputs_and_outputs(tmp_path):
    _child_flow(tmp_path / "child.flow.json", TestingDouble())
    sub = _sub_node("child.flow.json")
    sub.inputs.append(SubFlowInput("items", PropertyGetAny(GetGraphList("files"))))
    sub.outputs.append(SubFlowOutput("items", PropertySetAny(SetGraphList("files"))))
    after = ActionsNode()
    after.instructions.instructions.append(TestingPush("after"))
    graph = build_graph()
    graph.variables.declare("a", "number", 5)
    graph.variables.declare("res", "number", 0)
    graph.lists.declare("files", "string", ["parent"])
    _linear(graph, sub, after)
    graph.save(str(tmp_path / "parent.flow.json"))
    graph = Graph.load(str(tmp_path / "parent.flow.json"))

    # workdir elsewhere: the file must resolve against the parent's folder
    workdir = tmp_path / "elsewhere"
    workdir.mkdir()
    ctx = Context(graph=graph, workdir=str(workdir), logger=lambda lvl, msg: None)
    processor = GraphProcessor(graph)
    await processor.run(ctx)

    assert processor.failed_nodes == []
    assert graph.variables.get("res") == 10
    assert graph.lists.get("files").items == ["parent", "child"]
    assert trace(graph) == ["after"]
    assert GlobalScope.instance().variables.get("touched") == "yes"
    child = Graph.load(str(tmp_path / "child.flow.json"))
    assert child.variables.get("y") == 0          # file untouched


async def test_subflow_parallel_calls_are_isolated(tmp_path):
    _child_flow(tmp_path / "child.flow.json", TestingDouble())
    graph = build_graph()
    graph.variables.declare("a", "number", 5)
    graph.variables.declare("b", "number", 7)
    start = next(iter(graph.nodes_of_type(StartNode)))
    for x, y in (("a", "res"), ("b", "res2")):
        node = graph.add_node(_sub_node("child.flow.json", x=x, y=y))
        graph.connect(start, "out", node, "in")
    graph.save(str(tmp_path / "parent.flow.json"))
    graph = Graph.load(str(tmp_path / "parent.flow.json"))
    await GraphProcessor(graph).run(ctx_for(graph))
    assert graph.variables.get("res") == 10
    assert graph.variables.get("res2") == 14


async def test_subflow_unknown_binding_fails_node(tmp_path):
    _child_flow(tmp_path / "child.flow.json", TestingDouble())
    sub = _sub_node("child.flow.json")
    sub.inputs.append(SubFlowInput("nope", PropertyGetAny(GetGraphVariable("a"))))
    after = ActionsNode()
    after.instructions.instructions.append(TestingPush("after"))
    graph = _parent(tmp_path, sub, after)
    processor = GraphProcessor(graph)
    await processor.run(ctx_for(graph))
    assert processor.failed_nodes == [sub.name]
    assert trace(graph) == []


async def test_subflow_failure_propagates(tmp_path):
    _child_flow(tmp_path / "child.flow.json", TestingRaise())
    after = ActionsNode()
    after.instructions.instructions.append(TestingPush("after"))
    sub = _sub_node("child.flow.json")
    graph = _parent(tmp_path, sub, after)
    processor = GraphProcessor(graph)
    await processor.run(ctx_for(graph))
    assert processor.failed_nodes and trace(graph) == []

    graph.node_by_guid(sub.guid).fail_on_error = False
    processor = GraphProcessor(graph)
    await processor.run(ctx_for(graph))
    assert processor.failed_nodes == [] and trace(graph) == ["after"]


async def test_subflow_isolated_globals(tmp_path):
    _child_flow(tmp_path / "child.flow.json", TestingDouble())
    sub = _sub_node("child.flow.json")
    sub.share_globals = False
    sub.outputs.append(SubFlowOutput("x", PropertySetAny(SetGlobalVariable("got_x"))))
    graph = _parent(tmp_path, sub)
    await GraphProcessor(graph).run(ctx_for(graph))
    assert graph.variables.get("res") == 10
    assert GlobalScope.instance().variables.get("touched") is None
    assert GlobalScope.instance().variables.get("got_x") == 5   # outputs still reach the caller


async def test_subflow_recursion_is_bounded(tmp_path):
    graph = build_graph()
    sub = SubGraphNode()
    sub.file = "self.flow.json"
    _linear(graph, sub)
    graph.save(str(tmp_path / "self.flow.json"))
    graph = Graph.load(str(tmp_path / "self.flow.json"))
    processor = GraphProcessor(graph)
    await asyncio.wait_for(processor.run(ctx_for(graph)), timeout=20)
    assert processor.failed_nodes == [sub.name]


def test_subflow_bindings_in_refs_and_rename(tmp_path):
    from polytess.core.refs import find_references, rename_references
    graph = build_graph()
    graph.variables.declare("a", "number", 5)
    graph.variables.declare("res", "number", 0)
    sub = _sub_node("child.flow.json")
    _linear(graph, sub)
    assert [r.access for r in find_references(graph, "res", "graph")] == ["write"]
    assert [r.access for r in find_references(graph, "a", "graph")] == ["read"]
    assert find_references(graph, "x", "graph") == []           # sub-flow param
    assert rename_references(graph, "a", "a2", "graph") == 1
    assert sub.inputs[0].value.source.name == "a2" and sub.inputs[0].param == "x"


def test_subflow_bindings_flow_builder_roundtrip():
    from polytess.graph.flow_builder import build_flow, flow_to_data
    result = build_flow({
        "variables": [{"name": "a", "type": "number", "value": 2},
                      {"name": "res", "type": "number", "value": 0}],
        "lists": [{"name": "files", "type": "string", "items": []}],
        "nodes": [{"id": "sub", "kind": "subworkflow", "file": "c.flow.json",
                   "inputs": {"x": {"var": "a"}, "n": 3, "items": {"var": "files"}},
                   "outputs": {"y": "res", "items": "files", "g": {"global": "out"}},
                   "share_globals": False}],
        "edges": [{"from": "start", "to": "sub"}, {"from": "sub", "to": "exit"}]})
    assert result.ok, result.warnings
    spec = next(n for n in flow_to_data(result.graph)["nodes"]
                if n.get("kind") == "subworkflow")
    assert spec["inputs"] == {"x": {"var": "a"}, "n": 3, "items": {"var": "files"}}
    assert spec["outputs"] == {"y": "res", "items": "files", "g": {"global": "out"}}
    assert spec["share_globals"] is False and "fail_on_error" not in spec
    node = next(iter(result.graph.nodes_of_type(SubGraphNode)))
    assert type(node.inputs[2].value.source).__name__ == "GetGraphList"
    assert type(node.outputs[1].target.source).__name__ == "SetGraphList"


def test_cli_run_exit_code_reflects_failed_nodes(tmp_path):
    from polytess.cli import main
    for name, instruction, expected in (("ok", TestingPush("x"), 0),
                                        ("bad", TestingRaise(), 1)):
        graph = build_graph()
        actions = ActionsNode()
        actions.instructions.instructions.append(instruction)
        _linear(graph, actions)
        path = str(tmp_path / f"{name}.flow.json")
        graph.save(path)
        assert main(["run", path]) == expected
