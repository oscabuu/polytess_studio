# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""Flow lifecycle: branching, revisions, history snapshots, promote and
structural diffs."""

import json
import os

import pytest

from polytess.graph.lineage import (branch_file_path, branch_graph,
                                    diff_graphs, find_parent_path,
                                    list_history, promote_graph,
                                    save_with_history)
from polytess.graph.model import Graph
from polytess.graph.nodes import ActionsNode
from polytess.library.instructions.instruction_log_message import LogMessage
from polytess.library.instructions.instruction_set_string import SetString


def _make_graph(name="Pipeline") -> Graph:
    graph = Graph(name)
    graph.ensure_endpoints()
    node = ActionsNode()
    node.custom_name = "Prepare"
    node.instructions.instructions.append(LogMessage("hello"))
    graph.add_node(node)
    graph.variables.declare("deck", "string", "MR_A")
    return graph


def test_branch_keeps_family_and_guids():
    graph = _make_graph()
    branch = branch_graph(graph, "test-modes")
    assert branch.lineage.flow_id == graph.lineage.flow_id
    assert branch.lineage.branch == "test-modes"
    assert branch.lineage.parent_branch == "main"
    assert {n.guid for n in branch.nodes} == {n.guid for n in graph.nodes}
    # deep copy: edits do not leak back
    branch.variables.set("deck", "OTHER")
    assert graph.variables.get("deck") == "MR_A"


def test_save_bumps_revision_and_snapshots(tmp_path):
    graph = _make_graph()
    path = str(tmp_path / "pipeline.flow.json")
    save_with_history(graph, path)
    save_with_history(graph, path)
    assert graph.lineage.revision == 2
    snapshots = list_history(path, graph.lineage.flow_id)
    assert len(snapshots) == 2
    assert os.path.basename(snapshots[0]) == "main-r2.flow.json"
    # lineage survives the file round-trip
    loaded = Graph.load(path)
    assert loaded.lineage.flow_id == graph.lineage.flow_id
    assert loaded.lineage.revision == 2


def test_branch_paths():
    assert branch_file_path("/x/pipe.flow.json", "test") \
        == "/x/pipe@test.flow.json"
    assert branch_file_path("/x/pipe@old.flow.json", "new") \
        == "/x/pipe@new.flow.json"


def test_diff_reports_changes():
    graph = _make_graph()
    branch = branch_graph(graph, "variant")
    # change a param, add a node, add a variable
    prepare = next(n for n in branch.nodes if n.custom_name == "Prepare")
    prepare.instructions.instructions[0].message = \
        LogMessage("changed").message
    extra = ActionsNode()
    extra.custom_name = "Extra Step"
    extra.instructions.instructions.append(SetString())
    branch.add_node(extra)
    branch.variables.declare("mode", "string", "fast")

    diff = diff_graphs(graph, branch)
    assert diff.nodes_added == ["Extra Step"]
    assert not diff.nodes_removed
    assert any("Prepare" in line for line in diff.nodes_changed)
    assert "mode" in diff.variables_changed
    assert "node" in diff.summary()

    assert diff_graphs(graph, branch_graph(graph, "same")).is_empty


def test_promote_replaces_parent_and_keeps_history(tmp_path):
    graph = _make_graph()
    parent_path = str(tmp_path / "pipeline.flow.json")
    save_with_history(graph, parent_path)              # main·r1

    branch = branch_graph(graph, "variant")
    branch.variables.set("deck", "MR_B")
    branch_path = branch_file_path(parent_path, "variant")
    save_with_history(branch, branch_path)             # variant·r1
    assert find_parent_path(branch_path) == parent_path

    promoted = promote_graph(branch, parent_path)
    assert promoted.lineage.branch == "main"           # keeps parent identity
    assert promoted.lineage.parent_branch == "variant"

    reloaded = Graph.load(parent_path)
    assert reloaded.variables.get("deck") == "MR_B"  # content promoted
    snapshots = [os.path.basename(p)
                 for p in list_history(parent_path, graph.lineage.flow_id)]
    assert "main-r1.flow.json" in snapshots            # old state preserved


def test_promote_refuses_foreign_family(tmp_path):
    graph = _make_graph()
    parent_path = str(tmp_path / "pipeline.flow.json")
    save_with_history(graph, parent_path)
    stranger = _make_graph("Other")                    # different flow_id
    with pytest.raises(ValueError, match="famil"):
        promote_graph(stranger, parent_path)


def test_old_files_without_lineage_load(tmp_path):
    from polytess.core.serialization import to_data as serialize
    graph = _make_graph()
    data = serialize(graph)
    del data["lineage"]
    path = tmp_path / "legacy.flow.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = Graph.load(str(path))
    assert loaded.lineage.branch == "main"             # fresh identity
    assert loaded.lineage.revision == 0
