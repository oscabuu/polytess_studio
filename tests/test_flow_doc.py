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
