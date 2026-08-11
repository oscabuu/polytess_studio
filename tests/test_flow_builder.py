# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Flow builder: simplified JSON -> Graph, registry validation, missing
blocks, param binding; chat markdown rendering."""

from polytess.graph.flow_builder import (build_flow, build_flow_registry_summary,
                                       flow_to_data, missing_blocks_prompt)
from polytess.graph.nodes import (ActionsNode, ConditionsNode, ExitNode,
                                StartNode, TriggerNode)


def _flow(**overrides):
    data = {
        "name": "Test Flow",
        "variables": [{"name": "deck", "type": "string", "value": "MR_001"}],
        "nodes": [
            {"id": "prep", "kind": "actions", "name": "Vorbereiten",
             "instructions": [
                 {"type": "CreateFolder", "params": {"path": "results"}},
                 {"type": "LogMessage",
                  "params": {"message": {"template": "Deck {deck}"}}},
             ]},
            {"id": "chk", "kind": "conditions", "mode": "or",
             "conditions": [
                 {"type": "FileExists", "params": {"path": "out.inp"}}]},
        ],
        "edges": [
            {"from": "start", "to": "prep"},
            {"from": "prep", "to": "chk"},
            {"from": "chk", "port": "success", "to": "exit"},
            {"from": "chk", "port": "fail", "to": "prep"},
        ],
    }
    data.update(overrides)
    return data


def test_build_flow_basic():
    result = build_flow(_flow())
    assert result.ok, (result.errors, result.missing)
    graph = result.graph
    assert graph.name == "Test Flow"
    assert graph.variables.get("deck") == "MR_001"

    actions = next(iter(graph.nodes_of_type(ActionsNode)))
    assert actions.custom_name == "Vorbereiten"
    assert len(actions.instructions) == 2
    create, log = list(actions.instructions)
    assert create.path.source.value == "results"    # constant path source

    conditions = next(iter(graph.nodes_of_type(ConditionsNode)))
    assert conditions.check_mode == "or"
    assert len(conditions.conditions) == 1

    # edges: start->prep, prep->chk, chk success->exit, chk fail->prep
    assert len(graph.edges) == 4
    start = next(iter(graph.nodes_of_type(StartNode)))
    assert graph.children(start) == [actions]
    assert graph.children(conditions, "success") == \
        [next(iter(graph.nodes_of_type(ExitNode)))]
    assert graph.children(conditions, "fail") == [actions]

    # layout: columns increase along the chain
    assert start.x < actions.x < conditions.x


def _ctx(graph):
    from polytess.core import Context, GlobalScope
    GlobalScope.reset()
    return Context(graph=graph)


def test_template_and_var_params():
    result = build_flow(_flow())
    graph = result.graph
    actions = next(iter(graph.nodes_of_type(ActionsNode)))
    log = list(actions.instructions)[1]
    ctx = _ctx(graph)
    assert log.message.get(ctx) == "Deck MR_001"


def test_missing_blocks_are_reported():
    data = _flow()
    data["nodes"][0]["instructions"].append(
        {"type": "RunFemfatAnalysis", "params": {"job": "x"}})
    result = build_flow(data)
    assert result.missing == ["RunFemfatAnalysis"]
    assert not result.ok
    assert result.graph is not None          # baubar, Block bleibt offen

    prompt = missing_blocks_prompt(result.missing, "Test Flow")
    assert "RunFemfatAnalysis" in prompt
    assert "Custom Instructions" in prompt


def test_unknown_field_is_warning_not_error():
    data = _flow()
    data["nodes"][0]["instructions"][0]["params"]["nope"] = 1
    result = build_flow(data)
    assert result.graph is not None
    assert any("nope" in w for w in result.warnings)


def test_trigger_and_title_lookup():
    data = {
        "nodes": [
            {"id": "t", "kind": "trigger",
             "event": {"type": "On Timer", "params": {}}},
            {"id": "a", "kind": "actions", "instructions": [
                {"type": "Log Message", "params": {"message": "hi"}}]},
        ],
        "edges": [{"from": "t", "to": "a"}],
    }
    result = build_flow(data)
    assert not result.missing                 # Titel-Lookup findet die Klassen
    trigger = next(iter(result.graph.nodes_of_type(TriggerNode)))
    assert trigger.event is not None


def test_registry_summary_lists_fields():
    summary = build_flow_registry_summary()
    assert "LogMessage" in summary
    assert "FileExists" in summary
    assert "### Events" in summary


def test_flow_to_data_roundtrip():
    """Export of a built graph rebuilds to the same structure."""
    graph = build_flow(_flow()).graph
    data = flow_to_data(graph)

    assert data["name"] == "Test Flow"
    assert {"name": "deck", "type": "string", "value": "MR_001"} \
        in data["variables"]
    kinds = [n["kind"] for n in data["nodes"]]
    assert kinds.count("actions") == 1 and kinds.count("conditions") == 1
    actions = next(n for n in data["nodes"] if n["kind"] == "actions")
    assert actions["name"] == "Vorbereiten"
    types = [i["type"] for i in actions["instructions"]]
    assert types == ["CreateFolder", "LogMessage"]
    log_params = actions["instructions"][1]["params"]
    assert log_params["message"] == {"template": "Deck {deck}"}

    # edges keep ports and the implicit start/exit ids
    assert {"from": "start", "to": actions["id"]} in data["edges"]
    conditions = next(n for n in data["nodes"] if n["kind"] == "conditions")
    assert {"from": conditions["id"], "port": "success",
            "to": "exit"} in data["edges"]

    # and the export builds back into an equivalent graph
    rebuilt = build_flow(data)
    assert rebuilt.ok, (rebuilt.errors, rebuilt.missing)
    assert len(rebuilt.graph.edges) == len(graph.edges)
    rebuilt_actions = next(iter(rebuilt.graph.nodes_of_type(ActionsNode)))
    ctx = _ctx(rebuilt.graph)
    assert list(rebuilt_actions.instructions)[1].message.get(ctx) \
        == "Deck MR_001"


def test_flow_to_data_preserves_layout_groups_and_notes():
    """The export carries variable groups, node positions, canvas groups
    and sticky notes — a modify-roundtrip must not destroy them."""
    from polytess.graph.model import Group, StickyNote

    graph = build_flow(_flow()).graph
    graph.variables.variable("deck").group = "Inputs"
    actions = next(iter(graph.nodes_of_type(ActionsNode)))
    actions.x, actions.y = 123.0, 456.0
    graph.groups.append(Group("Phase 1", 10, 20, 500, 400, "#ff0000"))
    graph.notes.append(StickyNote("Hint", "check the deck", 5, 6, 210, 150))

    data = flow_to_data(graph)
    deck = next(v for v in data["variables"] if v["name"] == "deck")
    assert deck["group"] == "Inputs"
    exported = next(n for n in data["nodes"] if n["kind"] == "actions")
    assert exported["x"] == 123.0 and exported["y"] == 456.0
    kinds = {n["kind"] for n in data["nodes"]}
    assert "start" in kinds and "exit" in kinds       # endpoints keep x/y too
    assert data["groups"][0]["title"] == "Phase 1"
    assert data["notes"][0]["content"] == "check the deck"

    rebuilt = build_flow(data)
    assert rebuilt.ok, (rebuilt.errors, rebuilt.missing)
    rgraph = rebuilt.graph
    assert rgraph.variables.variable("deck").group == "Inputs"
    ractions = next(iter(rgraph.nodes_of_type(ActionsNode)))
    assert (ractions.x, ractions.y) == (123.0, 456.0)  # layout NOT rerun
    assert rgraph.groups[0].title == "Phase 1"
    assert rgraph.groups[0].color == "#ff0000"
    assert rgraph.notes[0].content == "check the deck"

    # a brand-new node without x/y gets parked instead of reflowing all
    data["nodes"].append({"id": "extra", "kind": "actions",
                          "instructions": []})
    data["edges"].append({"from": "start", "to": "extra"})
    rebuilt2 = build_flow(data)
    ractions2 = next(n for n in rebuilt2.graph.nodes_of_type(ActionsNode)
                     if not n.custom_name)
    assert (next(n for n in rebuilt2.graph.nodes_of_type(ActionsNode)
                 if n.custom_name).x, ) == (123.0, )


def test_markdown_rendering():
    from polytess.gui.chat_view import markdown_to_html
    html = markdown_to_html(
        "Hallo **Welt** mit `code`\n\n```python\ndef f():\n    return 1\n```\n"
        "- eins\n- zwei\n")
    assert "<b>Welt</b>" in html
    assert "<pre" in html and "def" in html
    assert html.count("<li") == 2
    # HTML in user content must be escaped
    assert "<script" not in markdown_to_html("<script>alert(1)</script>")
