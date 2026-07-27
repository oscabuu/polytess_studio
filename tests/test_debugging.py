"""Tests: node breakpoints, pause/resume/step, variable reference search."""

import asyncio

import pytest

import polytess.library  # noqa: F401
from polytess.core import Context, GlobalScope, Instruction, meta
from polytess.core.refs import find_references
from polytess.graph import ActionsNode, Graph, GraphProcessor, NodeStatus, StartNode


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


@meta(title="Test Mark", category="Testing/Mark", hidden=True)
class TestingMark(Instruction):
    def __init__(self, tag: str = ""):
        super().__init__()
        self.tag = tag

    async def run(self, ctx):
        ctx.graph_lists.require("trace").push(self.tag)


def build_chain(tags):
    graph = Graph("t")
    graph.ensure_endpoints()
    start = next(iter(graph.nodes_of_type(StartNode)))
    previous = start
    nodes = []
    for tag in tags:
        node = graph.add_node(ActionsNode())
        node.custom_name = tag
        node.instructions.instructions.append(TestingMark(tag))
        graph.connect(previous, "out", node, "in")
        previous = node
        nodes.append(node)
    return graph, nodes


def trace(graph):
    lst = graph.lists.get("trace")
    return list(lst.items) if lst else []


def ctx_for(graph):
    return Context(graph=graph, logger=lambda l, m: None)


async def test_breakpoint_pauses_and_resume(tmp_path):
    graph, nodes = build_chain(["a", "b", "c"])
    nodes[1].breakpoint = True
    statuses = []
    processor = GraphProcessor(graph,
                               on_status=lambda n, s: statuses.append((n.name, s)))
    states = []
    processor.on_state.append(states.append)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.3)

    # paused BEFORE node b ran
    assert processor.is_paused
    assert trace(graph) == ["a"]
    assert ("b", NodeStatus.PAUSED) in statuses
    assert states[-1] == "paused"

    processor.resume()
    await asyncio.wait_for(task, timeout=5)
    assert trace(graph) == ["a", "b", "c"]
    assert not processor.is_paused


async def test_pause_and_step(tmp_path):
    graph, nodes = build_chain(["a", "b", "c"])
    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    processor.pause()                       # pause before anything starts
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.25)
    assert trace(graph) == []               # gated at the start node

    processor.step()                        # start node
    await asyncio.sleep(0.25)
    processor.step()                        # node a
    await asyncio.sleep(0.25)
    assert trace(graph) == ["a"]
    assert processor.is_paused              # still paused after the step

    processor.resume()                      # run to completion
    await asyncio.wait_for(task, timeout=5)
    assert trace(graph) == ["a", "b", "c"]


async def test_stop_while_paused(tmp_path):
    graph, nodes = build_chain(["a", "b"])
    nodes[0].breakpoint = True
    processor = GraphProcessor(graph)
    ctx = ctx_for(graph)
    task = asyncio.ensure_future(processor.run(ctx))
    await asyncio.sleep(0.2)
    assert processor.is_paused
    ctx.cancel()
    processor.stop()
    await asyncio.wait_for(task, timeout=5)
    assert trace(graph) == []


def test_breakpoint_serialization(tmp_path):
    graph, nodes = build_chain(["a"])
    nodes[0].breakpoint = True
    path = str(tmp_path / "bp.flow.json")
    graph.save(path)
    clone = Graph.load(path)
    reloaded = clone.node_by_guid(nodes[0].guid)
    assert reloaded.breakpoint is True


# --------------------------------------------------------------------------- #
# variable references
# --------------------------------------------------------------------------- #

async def test_find_references_read_write():
    from polytess.core.properties import (GetGraphVariable, GetStringFormat,
                                        PropertyGetString, PropertySetString,
                                        SetGraphVariable)
    from polytess.library.instructions.instruction_add_to_list import AddToList
    from polytess.library.instructions.instruction_loop_table import LoopTable
    from polytess.library.instructions.instruction_read_csv_to_table import ReadCsvToTable
    from polytess.library.instructions.instruction_set_string import SetString
    from polytess.library.instructions.instruction_wait_for_files import WaitForFiles

    graph = Graph("refs")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    node.custom_name = "Worker"

    writer = SetString()
    writer.target = PropertySetString(SetGraphVariable("case"))     # write case
    reader = SetString()
    reader.target = PropertySetString(SetGraphVariable("label"))    # write label
    reader.value = PropertyGetString(GetGraphVariable("case"))      # read case
    template = SetString()
    template.target = PropertySetString(SetGraphVariable("path"))   # write path
    template.value = PropertyGetString(GetStringFormat("out/{case}/x"))  # read case
    csv_reader = ReadCsvToTable("cfg.csv", "config")                # write config
    loop = LoopTable("config")                                      # read config
    loop.actions.instructions.append(AddToList("results"))          # write results
    wait = WaitForFiles("results")                                  # read results
    node.instructions.instructions += [writer, reader, template,
                                       csv_reader, loop, wait]

    refs_case = find_references(graph, "case", "graph")
    accesses = sorted(r.access for r in refs_case)
    assert accesses == ["read", "read", "write"]
    assert all(r.node_name == "Worker" for r in refs_case)

    refs_config = find_references(graph, "config", "graph")
    assert {(r.access, r.detail) for r in refs_config} == {
        ("write", "SetGraphTable.name"), ("read", "GetGraphTable.name")}

    refs_results = find_references(graph, "results", "graph")
    assert sorted(r.access for r in refs_results) == ["read", "write"]
    # nested reference (inside the loop's action list) found
    assert any(r.detail == "SetGraphList.name" for r in refs_results)

    assert find_references(graph, "unknown_var", "graph") == []


async def test_find_references_scope_filter():
    from polytess.core.properties import (GetGlobalVariable, PropertyGetString,
                                        PropertySetString, SetGraphVariable)
    from polytess.library.instructions.instruction_set_string import SetString

    graph = Graph("scopes")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    inst = SetString()
    inst.target = PropertySetString(SetGraphVariable("x"))      # graph write
    inst.value = PropertyGetString(GetGlobalVariable("x"))      # global read
    node.instructions.instructions.append(inst)

    graph_refs = find_references(graph, "x", "graph")
    assert [r.access for r in graph_refs] == ["write"]
    global_refs = find_references(graph, "x", "global")
    assert [r.access for r in global_refs] == ["read"]
    assert len(find_references(graph, "x", "any")) == 2
