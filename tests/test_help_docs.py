# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""In-app manual, example gallery and tutorial flows."""

import os

import pytest

from polytess.graph.model import Graph
from polytess.gui.example_gallery import example_flows
from polytess.gui.help_browser import chapters


def test_manual_has_all_chapters():
    found = chapters()
    assert len(found) >= 9
    titles = [title for title, _path in found]
    assert any("Getting started" in t for t in titles)
    assert any("Concepts" in t for t in titles)
    for _title, path in found:
        text = open(path, encoding="utf-8").read()
        assert len(text) > 300, f"chapter too thin: {path}"


def test_gallery_lists_tutorials_and_examples():
    flows = example_flows()
    names = [os.path.basename(p) for _g, _d, p in flows]
    assert "tutorial_01_hello.flow.json" in names
    assert "tutorial_02_loops_and_conditions.flow.json" in names
    assert "tutorial_03_watch_folder.flow.json" in names
    # repo examples are discovered through install roots
    assert any("demo" in n for n in names)
    assert len(names) == len(set(names))          # deduplicated


@pytest.mark.parametrize("stem", [
    "tutorial_01_hello", "tutorial_02_loops_and_conditions",
    "tutorial_03_watch_folder"])
def test_tutorial_flows_load_and_resolve(stem):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "polytess", "assets", "examples",
                        f"{stem}.flow.json")
    graph = Graph.load(path)          # raises on unknown $type
    assert len(graph.nodes) >= 3
    assert graph.name.startswith("Tutorial")


def test_help_window_and_gallery_offscreen(qt_app):
    from polytess.gui.example_gallery import ExampleGalleryDialog
    from polytess.gui.help_browser import HelpWindow
    window = HelpWindow()
    assert window.chapter_list.count() >= 9
    window._show(0)
    assert "first flow" in window.viewer.toPlainText().lower()
    dialog = ExampleGalleryDialog()
    assert dialog.tree.topLevelItemCount() >= 1


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])
