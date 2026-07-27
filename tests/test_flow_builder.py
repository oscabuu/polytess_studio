# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""Flow builder: simplified JSON -> Graph, registry validation, missing
blocks, param binding; chat markdown rendering."""

from polytess.graph.flow_builder import (build_flow, build_flow_registry_summary,
                                       missing_blocks_prompt)
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
