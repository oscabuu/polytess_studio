# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Viewer input form (polytess.graph.inputs): derivation from a flow,
validation, applying values, vars files and the CLI commands."""

import json

from polytess.graph.flow_builder import build_flow, flow_to_data
from polytess.graph.inputs import (apply_values, input_spec, load_vars_file,
                                   save_vars_file, validate_values)


def _graph():
    return build_flow({
        "name": "Viewer Flow",
        "variables": [
            {"name": "deck", "type": "string", "value": "MR_001",
             "group": "Model",
             "form": {"label": "Deck name", "description": "Abaqus deck",
                      "required": True, "order": 2}},
            {"name": "cpus", "type": "integer", "value": 4, "group": "Model",
             "form": {"minimum": 1, "maximum": 64, "order": 1}},
            {"name": "solver", "type": "string", "value": "abaqus",
             "form": {"choices": ["abaqus", "simpack"]}},
            {"name": "model", "type": "path", "value": "",
             "form": {"path_kind": "file", "must_exist": True}},
            {"name": "result", "type": "string", "value": ""},
            {"name": "summary", "type": "string", "value": "",
             "form": {"mode": "output"}},
            {"name": "internal", "type": "string", "value": "x",
             "form": {"mode": "hidden"}},
            {"name": "forced", "type": "string", "value": "",
             "form": {"mode": "input"}},
        ],
        "lists": [{"name": "inputs", "type": "path", "items": ["a.inp"]},
                  {"name": "found", "type": "path", "items": []}],
        "nodes": [{"id": "a", "kind": "actions", "instructions": [
            {"type": "SetString",
             "params": {"value": {"var": "deck"}, "target": "result"}},
            {"type": "SetString",
             "params": {"value": {"var": "deck"}, "target": "summary"}},
            {"type": "SetString",
             "params": {"value": {"var": "deck"}, "target": "forced"}},
            {"type": "FindFiles",
             "params": {"pattern": "*.txt", "target_list": "found"}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph


def test_input_spec_rules_and_grouping():
    spec = input_spec(_graph())
    names = [f.name for f in spec.fields]
    # runtime-written -> hidden unless forced; hidden mode -> gone
    assert "result" not in names and "found" not in names
    assert "internal" not in names
    assert "forced" in names                     # mode input wins
    assert [f.name for f in spec.outputs] == ["summary"]
    # ungrouped first, then groups; order key inside a group
    assert spec.sections[0].title == ""
    assert spec.sections[1].title == "Model"
    assert [f.name for f in spec.sections[1].fields] == ["cpus", "deck"]
    deck = spec.field_named("deck")
    assert deck.label == "Deck name" and deck.required
    assert deck.description == "Abaqus deck" and deck.value == "MR_001"
    cpus = spec.field_named("cpus")
    assert cpus.label == "cpus" and cpus.minimum == 1 and cpus.maximum == 64
    inputs = spec.field_named("inputs")
    assert inputs.kind == "list" and inputs.value == ["a.inp"]
    assert spec.field_named("forced").status == "runtime"
    # JSON-able
    data = json.loads(json.dumps(spec.to_dict()))
    assert data["flow"] == "Viewer Flow" and data["outputs"][0]["name"] == "summary"


def test_validate_values(tmp_path):
    spec = input_spec(_graph())
    model = tmp_path / "model.inp"
    model.write_text("*HEADING\n")
    ok = {"deck": "MR_002", "cpus": 8, "solver": "simpack",
          "model": str(model)}
    assert validate_values(spec, ok) == []

    problems = validate_values(spec, {
        "deck": "", "cpus": 0.5, "solver": "nastran",
        "model": str(tmp_path / "missing.inp")})
    text = "\n".join(problems)
    assert "Deck name: required" in text
    assert "cpus: not a whole number" in text
    assert "solver: not one of abaqus, simpack" in text
    assert "model: file not found" in text
    assert validate_values(spec, {"cpus": 100})[0].startswith("cpus: above maximum 64")
    assert validate_values(spec, {"cpus": 0})[0].startswith("cpus: below minimum 1")
    # a folder where a file is required
    assert "file not found" in validate_values(spec, {"model": str(tmp_path)})[0]


def test_apply_values_and_vars_file(tmp_path):
    graph = _graph()
    unknown = apply_values(graph, {"deck": "MR_009", "cpus": 16,
                                   "inputs": ["x.inp", "y.inp"], "nope": 1})
    assert unknown == ["nope"]
    assert graph.variables.get("deck") == "MR_009"
    assert graph.variables.get("cpus") == 16
    assert list(graph.lists.get("inputs").items) == ["x.inp", "y.inp"]

    path = str(tmp_path / "preset.json")
    save_vars_file(path, {"deck": "MR_010", "cpus": 2})
    assert load_vars_file(path) == {"deck": "MR_010", "cpus": 2}


def test_form_metadata_round_trips_assistant_schema_and_file(tmp_path):
    from polytess.graph.model import Graph

    graph = _graph()
    data = flow_to_data(graph)
    deck = next(v for v in data["variables"] if v["name"] == "deck")
    assert deck["form"]["label"] == "Deck name" and deck["form"]["required"]
    result = next(v for v in data["variables"] if v["name"] == "result")
    assert "form" not in result
    rebuilt = build_flow(data).graph
    assert rebuilt.variables.variable("deck").form["label"] == "Deck name"
    # unknown keys are dropped
    junk = build_flow({"name": "j", "variables": [
        {"name": "a", "type": "string", "form": {"label": "A", "bogus": 1}}],
        "nodes": [], "edges": []}).graph
    assert junk.variables.variable("a").form == {"label": "A"}

    path = str(tmp_path / "viewer.flow.json")
    graph.save(path)
    loaded = Graph.load(path)
    assert loaded.variables.variable("deck").form["description"] == "Abaqus deck"
    assert loaded.lists.get("inputs").form == {}


def test_cli_inputs_and_vars_file(tmp_path, capsys):
    from polytess.cli import main

    flow = str(tmp_path / "v.flow.json")
    _graph().save(flow)

    assert main(["inputs", flow]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [s["title"] for s in out["sections"]] == ["", "Model"]

    template = str(tmp_path / "template.json")
    assert main(["inputs", flow, "--template", template]) == 0
    values = load_vars_file(template)
    assert values["deck"] == "MR_001" and values["inputs"] == ["a.inp"]
    assert "result" not in values

    # invalid preset -> exit 2 before anything runs
    bad = str(tmp_path / "bad.json")
    save_vars_file(bad, {"deck": "", "cpus": 999})
    assert main(["run", flow, "--vars-file", bad]) == 2
    err = capsys.readouterr().err
    assert "Deck name: required" in err and "above maximum" in err
