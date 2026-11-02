# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Kanban board core (polytess.graph.board): projection of a main
process, run state, running cards with predecessors, stale detection,
statistics and the CLI command."""

import json
import os

import pytest

from polytess.core.variables import GlobalScope
from polytess.graph.board import (ACTIVE, DONE, FAILED, PENDING, QUEUED,
                                  STALE, BoardRunner, BoardState, board_spec,
                                  state_path)
from polytess.graph.flow_builder import build_flow
from polytess.graph.model import Graph


@pytest.fixture(autouse=True)
def _globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


def _save(folder, name, spec):
    result = build_flow(spec)
    assert result.ok, (result.errors, result.missing)
    path = os.path.join(folder, name)
    result.graph.save(path)
    return path


def _sub(name, fail=False):
    steps = [{"type": "SetNumber", "params": {"value": 7, "target": "y"}}]
    if fail:
        steps = [{"type": "ReadTextFile",
                  "params": {"path": "/nonexistent/x.txt", "target": "s"}}]
    return {"name": name,
            "variables": [{"name": "x", "type": "number", "value": 1},
                          {"name": "y", "type": "number", "value": 0},
                          {"name": "s", "type": "string", "value": ""}],
            "nodes": [{"id": "a", "kind": "actions", "instructions": steps}],
            "edges": [{"from": "start", "to": "a"}, {"from": "a", "to": "exit"}]}


def _main(tmp_path, fail_card=None):
    """prep → mesh → (static, modal); static → report; plus a conditions
    node between mesh and modal (conditional card)."""
    for name in ("prep", "mesh", "static", "modal", "report"):
        _save(tmp_path, f"{name}.flow.json", _sub(name, fail=(name == fail_card)))

    def card(i, file, **kw):
        spec = {"id": i, "kind": "subworkflow", "file": file, "name": i,
                "inputs": {"x": {"var": "a"}}, "outputs": {"y": "res_" + i}}
        spec.update(kw)
        return spec
    main = {
        "name": "Main",
        "variables": [{"name": "a", "type": "number", "value": 5}]
        + [{"name": f"res_{i}", "type": "number", "value": 0}
           for i in ("prep", "mesh", "static", "modal", "report")],
        "nodes": [card("prep", "prep.flow.json"), card("mesh", "mesh.flow.json"),
                  card("static", "static.flow.json"),
                  {"id": "chk", "kind": "conditions", "conditions": [
                      {"type": "CompareNumber", "params": {}}]},
                  card("modal", "modal.flow.json"),
                  card("report", "report.flow.json")],
        "edges": [{"from": "start", "to": "prep"}, {"from": "prep", "to": "mesh"},
                  {"from": "mesh", "to": "static"}, {"from": "mesh", "to": "chk"},
                  {"from": "chk", "port": "success", "to": "modal"},
                  {"from": "static", "to": "report"},
                  {"from": "report", "to": "exit"}],
    }
    path = _save(tmp_path, "main.flow.json", main)
    return Graph.load(path)


def test_board_spec_dependencies_levels_and_conditional(tmp_path):
    spec = board_spec(_main(tmp_path))
    titles = {c.title: c for c in spec.cards}
    assert set(titles) == {"prep", "mesh", "static", "modal", "report"}
    assert titles["prep"].predecessors == []
    assert [spec.card(p).title for p in titles["mesh"].predecessors] == ["prep"]
    assert [spec.card(p).title for p in titles["report"].predecessors] == ["static"]
    assert titles["modal"].conditional and not titles["static"].conditional
    assert (titles["prep"].level, titles["mesh"].level, titles["static"].level,
            titles["report"].level) == (0, 1, 2, 3)
    assert [spec.card(g).title for g in spec.ancestors(titles["report"].guid)] \
        == ["prep", "mesh", "static"]
    assert spec.problems == []
    assert json.loads(json.dumps(spec.to_dict()))["flow"] == "Main"


def test_board_spec_reports_cycles_and_missing_files():
    main = {"name": "Cyc", "nodes": [
        {"id": "a", "kind": "subworkflow", "file": "a.flow.json"},
        {"id": "b", "kind": "subworkflow", "file": ""}],
        "edges": [{"from": "start", "to": "a"}, {"from": "a", "to": "b"},
                  {"from": "b", "to": "a"}]}
    spec = board_spec(build_flow(main).graph)
    assert any("cycle" in p for p in spec.problems)
    assert any("no workflow file" in p for p in spec.problems)


async def test_runner_runs_plan_with_predecessors_and_auto_advance(tmp_path):
    graph = _main(tmp_path)
    events = []
    runner = BoardRunner(graph, on_change=lambda g, s: events.append((g, s)))
    report = runner.spec.card_by_title("report")
    assert [c.title for c in runner.plan(report.guid)] \
        == ["prep", "mesh", "static", "report"]
    assert [c.title for c in runner.ready_cards()] == ["prep"]

    ran = await runner.run_plan(report.guid, auto_advance=True)
    titles = [runner.spec.card(g).title for g in ran]
    # predecessors first, then report, then auto-advance picks up modal
    assert titles == ["prep", "mesh", "static", "report", "modal"]
    assert all(runner.status(c.guid) == DONE for c in runner.spec.cards)
    assert graph.variables.get("res_report") == 7
    statuses = [s for g, s in events if g == report.guid]
    assert statuses[:2] == [QUEUED, ACTIVE] and statuses[-1] == DONE

    # state persisted next to the flow, with history and a log per card
    assert os.path.isfile(state_path(graph.path))
    state = BoardState.load(state_path(graph.path))
    assert state.status(report.guid) == DONE
    assert len(state.history) == 5 and state.variables["res_mesh"] == 7
    assert os.path.isfile(state.card(report.guid).log)
    summary = state.summary(runner.spec)
    assert summary["counts"][DONE] == 5 and summary["progress"] == 1.0
    assert summary["success_rate"] == 1.0 and "streak" not in summary

    # reopening: results are recognized (same inputs) -> nothing to run
    again = BoardRunner(Graph.load(graph.path))
    assert again.ready_cards() == []
    assert again.unfinished_predecessors(report.guid) == []


async def test_runner_marks_stale_when_inputs_change(tmp_path):
    graph = _main(tmp_path)
    runner = BoardRunner(graph)
    await runner.run_all()
    assert all(runner.status(c.guid) == DONE for c in runner.spec.cards)
    graph.variables.set("a", 6)
    runner.refresh_stale()
    assert all(runner.status(c.guid) == STALE for c in runner.spec.cards)
    assert [c.title for c in runner.ready_cards()] == ["prep"]
    mesh = runner.spec.card_by_title("mesh")
    runner.reset(mesh.guid)
    assert runner.status(mesh.guid) == PENDING
    assert runner.status(runner.spec.card_by_title("report").guid) == PENDING
    assert runner.status(runner.spec.card_by_title("prep").guid) == STALE


async def test_runner_failure_stops_plan_and_unqueues(tmp_path):
    graph = _main(tmp_path, fail_card="mesh")
    runner = BoardRunner(graph)
    report = runner.spec.card_by_title("report")
    ran = await runner.run_plan(report.guid)
    assert [runner.spec.card(g).title for g in ran] == ["prep", "mesh"]
    mesh = runner.spec.card_by_title("mesh")
    assert runner.status(mesh.guid) == FAILED
    assert runner.status(runner.spec.card_by_title("static").guid) == PENDING
    assert runner.status(report.guid) == PENDING
    assert runner.state.card(mesh.guid).error
    summary = runner.state.summary(runner.spec)
    assert summary["most_failing"] == "mesh"
    assert summary["estimated_remaining"] >= 0


def test_cli_board_show_run_reset(tmp_path, capsys):
    from polytess.cli import main
    graph = _main(tmp_path)
    assert main(["board", graph.path]) == 0
    out = capsys.readouterr().out
    assert "0/5 done" in out and "[pending] mesh  ← prep" in out

    assert main(["board", graph.path, "--run", "mesh"]) == 0
    out = capsys.readouterr().out
    assert "2/5 done" in out and "[done   ] mesh" in out

    assert main(["board", graph.path, "--all"]) == 0
    assert "5/5 done" in capsys.readouterr().out

    assert main(["board", graph.path, "--reset", "all"]) == 0
    assert "0/5 done" in capsys.readouterr().out

    assert main(["board", graph.path, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["cards"]) == 5


def test_board_spec_nested_children_with_depth(tmp_path):
    """Cards list the Sub-Workflow nodes of their own flow as sub-steps,
    recursively down to the requested depth."""
    from polytess.graph.board import flatten_steps
    _save(tmp_path, "leaf.flow.json", _sub("leaf"))
    _save(tmp_path, "mid.flow.json", {
        "name": "mid",
        "variables": [{"name": "x", "type": "number", "value": 1},
                      {"name": "y", "type": "number", "value": 0}],
        "nodes": [{"id": "l1", "kind": "subworkflow", "file": "leaf.flow.json",
                   "name": "Leaf One", "inputs": {"x": {"var": "x"}}, "outputs": {"y": "y"}},
                  {"id": "l2", "kind": "subworkflow", "file": "leaf.flow.json",
                   "name": "Leaf Two"}],
        "edges": [{"from": "start", "to": "l1"}, {"from": "l1", "to": "l2"},
                  {"from": "l2", "to": "exit"}]})
    path = _save(tmp_path, "top.flow.json", {
        "name": "top",
        "variables": [{"name": "a", "type": "number", "value": 5},
                      {"name": "r", "type": "number", "value": 0}],
        "nodes": [{"id": "m", "kind": "subworkflow", "file": "mid.flow.json",
                   "name": "Middle", "inputs": {"x": {"var": "a"}}, "outputs": {"y": "r"}},
                  {"id": "p", "kind": "subworkflow", "file": "leaf.flow.json",
                   "name": "Plain"}],
        "edges": [{"from": "start", "to": "m"}, {"from": "m", "to": "p"},
                  {"from": "p", "to": "exit"}]})
    graph = Graph.load(path)
    spec = board_spec(graph)                              # default depth 1
    middle = spec.card_by_title("Middle")
    assert [c["title"] for c in middle.children] == ["Leaf One", "Leaf Two"]
    assert middle.children[0]["children"] == []           # depth exhausted
    assert spec.card_by_title("Plain").children == []     # leaf has no sub-flows
    assert board_spec(graph, depth=0).card_by_title("Middle").children == []
    assert [(c["title"], d) for c, d in flatten_steps(middle.children)] \
        == [("Leaf One", 0), ("Leaf Two", 0)]
    # a card's dict (CLI --json) carries the children
    assert json.loads(json.dumps(spec.to_dict()))["cards"][0]["children"][0]["title"] == "Leaf One"


async def test_nested_progress_is_relayed_to_the_board(tmp_path):
    """Node statuses of nested sub-flows reach the BoardRunner's on_progress
    (SubGraphNode relays them), keyed by the card they belong to."""
    _save(tmp_path, "leaf.flow.json", _sub("leaf"))
    _save(tmp_path, "mid.flow.json", {
        "name": "mid",
        "variables": [{"name": "x", "type": "number", "value": 1},
                      {"name": "y", "type": "number", "value": 0}],
        "nodes": [{"id": "l1", "kind": "subworkflow", "file": "leaf.flow.json",
                   "name": "Leaf One", "inputs": {"x": {"var": "x"}}, "outputs": {"y": "y"}}],
        "edges": [{"from": "start", "to": "l1"}, {"from": "l1", "to": "exit"}]})
    path = _save(tmp_path, "top.flow.json", {
        "name": "top",
        "variables": [{"name": "a", "type": "number", "value": 5},
                      {"name": "r", "type": "number", "value": 0}],
        "nodes": [{"id": "m", "kind": "subworkflow", "file": "mid.flow.json",
                   "name": "Middle", "inputs": {"x": {"var": "a"}}, "outputs": {"y": "r"}}],
        "edges": [{"from": "start", "to": "m"}, {"from": "m", "to": "exit"}]})
    graph = Graph.load(path)
    seen = []
    runner = BoardRunner(graph, on_progress=lambda g, n, s: seen.append((g, n.guid, s.value)))
    middle = runner.spec.card_by_title("Middle")
    leaf_guid = middle.children[0]["guid"]
    assert await runner.run_card(middle.guid) == DONE
    assert (middle.guid, leaf_guid, "running") in seen
    assert (middle.guid, leaf_guid, "success") in seen
    assert graph.variables.get("r") == 7
