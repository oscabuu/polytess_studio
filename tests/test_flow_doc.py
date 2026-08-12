# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Flow documentation PDF: generation, links, chapter order."""

import pytest

reportlab = pytest.importorskip("reportlab")

from polytess.graph.flow_doc import _node_order, generate_flow_doc
from polytess.graph.model import Graph
from polytess.graph.nodes import ActionsNode, ConditionsNode, StartNode
from polytess.library.conditions.condition_file_exists import FileExists
from polytess.library.instructions.instruction_log_message import LogMessage


def _make_graph() -> Graph:
    graph = Graph("Doc Test Flow")
    graph.ensure_endpoints()
    prepare = ActionsNode()
    prepare.custom_name = "Prepare"
    prepare.instructions.instructions.append(LogMessage("hello"))
    prepare.x = 0
    graph.add_node(prepare)
    check = ConditionsNode()
    check.custom_name = "Ready?"
    check.conditions.conditions.append(FileExists("out.txt"))
    check.x = 300
    graph.add_node(check)
    start = next(iter(graph.nodes_of_type(StartNode)))
    graph.connect(start, "out", prepare, "in")
    graph.connect(prepare, "out", check, "in")
    graph.variables.declare("deck", "string", "MR_A")
    return graph


def test_generate_pdf_with_links(tmp_path):
    graph = _make_graph()
    out = str(tmp_path / "doc.pdf")
    assert generate_flow_doc(graph, out) == out

    data = (tmp_path / "doc.pdf").read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 5000
    assert b"/Link" in data                    # clickable annotations
    assert b"/Annots" in data                  # annotation arrays on pages


def test_chapter_order_is_bfs():
    graph = _make_graph()
    names = [n.name for n in _node_order(graph)]
    assert names.index("Start") < names.index("Prepare") < names.index("Ready?")
    assert len(names) == len(graph.nodes)


def _story_text(graph) -> str:
    """All rendered text of the document (font subsetting makes literal
    search inside the PDF bytes unreliable — inspect the story instead)."""
    from polytess.graph.flow_doc import (_build_story, _register_fonts,
                                         _styles)
    from reportlab.platypus import Table

    _register_fonts()
    parts = []
    for flowable in _build_story(graph, _styles()):
        text = getattr(flowable, "text", None)
        if text:
            parts.append(str(text))
        if isinstance(flowable, Table):
            for row in flowable._cellvalues:
                for cell in row:
                    parts.append(getattr(cell, "text", None) or str(cell))
    return "\n".join(parts)


def test_doc_regenerates_fresh_every_time(tmp_path):
    """Exporting, changing the flow, exporting again produces a doc with
    the NEW state — there is no caching anywhere."""
    graph = _make_graph()
    out = tmp_path / "doc.pdf"
    generate_flow_doc(graph, str(out))
    first_bytes = out.read_bytes()
    assert "MARKER_AFTER_EDIT" not in _story_text(graph)

    graph.variables.set("deck", "MARKER_AFTER_EDIT")
    prepare = next(n for n in graph.nodes if n.name == "Prepare")
    prepare.custom_name = "Prepare Renamed"
    text = _story_text(graph)                   # regenerated content
    assert "MARKER_AFTER_EDIT" in text
    assert "Prepare Renamed" in text
    generate_flow_doc(graph, str(out))          # same path, overwrite works
    assert out.read_bytes() != first_bytes


def test_doc_shows_canvas_and_variable_groups():
    from polytess.graph.model import Group

    graph = _make_graph()
    prepare = next(n for n in graph.nodes if n.name == "Prepare")
    graph.groups.append(Group("Preparation Phase",
                              prepare.x - 40, prepare.y - 40, 320, 240))
    graph.variables.variable("deck").group = "Model Inputs"
    graph.variables.declare("speed", "number", 1)     # stays ungrouped

    text = _story_text(graph)
    assert "Preparation Phase" in text        # canvas group at the chapter
    assert "Model Inputs" in text             # variable group in Blackboard


def test_doc_resolves_branches_and_loop_bodies():
    """Branch nodes and loop bodies are expanded item by item — not
    summarized as 'N nested steps/checks'."""
    from polytess.core.conditions import Branch
    from polytess.graph.nodes import BranchNode
    from polytess.library.conditions.condition_compare_number import \
        CompareNumber
    from polytess.library.instructions.instruction_loop_range import LoopRange

    graph = _make_graph()
    branch_node = BranchNode()
    branch_node.custom_name = "Route"
    case_a = Branch("fast lane")
    case_a.conditions.conditions.append(CompareNumber(1, "<", 2))
    case_a.instructions.instructions.append(LogMessage("taking fast lane"))
    loop = LoopRange(0, 3, 1)
    loop.actions.instructions.append(LogMessage("inner loop step"))
    case_b = Branch("fallback")
    case_b.instructions.instructions.append(loop)
    branch_node.branches.branches.append(case_a)
    branch_node.branches.branches.append(case_b)
    graph.add_node(branch_node)

    text = _story_text(graph)
    assert "fast lane" in text
    assert "Compare Number" in text            # branch condition expanded
    assert "taking fast lane" in text          # branch instruction expanded
    assert "inner loop step" in text           # nested loop body expanded
    assert "nested steps" not in text
    assert "nested checks" not in text
