# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""polytess Viewer (polytess.viewer): form widgets, presets, form page
run, board page run with auto-advance, start window routing."""

import asyncio
import os

import pytest

from polytess.core.app_settings import AppSettings
from polytess.core.variables import GlobalScope
from polytess.graph.board import DONE, PENDING
from polytess.graph.flow_builder import build_flow
from polytess.graph.model import Graph

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "examples", "viewer")


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.setenv("POLYTESS_USER_DIR", str(tmp_path / "userdir"))
    AppSettings.reset(path="", use_command_server=False, viewer_celebrations="off")
    GlobalScope.reset()
    yield
    GlobalScope.reset()


def _demo_copy(tmp_path):
    import shutil
    folder = tmp_path / "demo"
    shutil.copytree(EXAMPLES, folder,
                    ignore=shutil.ignore_patterns("*.board.json", ".runs"))
    return folder


def test_form_widgets_values_validation_and_presets(tmp_path):
    from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox
    from polytess.graph.inputs import input_spec
    from polytess.viewer import presets
    from polytess.viewer.form import InputForm, _ListEditor, _PathField

    graph = build_flow({
        "name": "F",
        "variables": [
            {"name": "name", "type": "string", "value": "a", "group": "G",
             "form": {"label": "Name", "required": True}},
            {"name": "n", "type": "integer", "value": 3,
             "form": {"minimum": 1, "maximum": 9}},
            {"name": "x", "type": "number", "value": 1.5},
            {"name": "flag", "type": "bool", "value": True},
            {"name": "mode", "type": "string", "value": "b",
             "form": {"choices": ["a", "b"]}},
            {"name": "folder", "type": "path", "value": "",
             "form": {"path_kind": "folder", "must_exist": True, "required": True}},
        ],
        "lists": [{"name": "files", "type": "path", "items": ["x.txt"]}],
        "nodes": [], "edges": []}).graph
    spec = input_spec(graph)
    form = InputForm(spec)
    editors = {name: editor for name, (f, editor) in form._editors.items()}
    assert isinstance(editors["n"], QSpinBox) and isinstance(editors["x"], QDoubleSpinBox)
    assert isinstance(editors["flag"], QComboBox) and isinstance(editors["mode"], QComboBox)
    assert isinstance(editors["folder"], _PathField)
    assert isinstance(editors["files"], _ListEditor)
    values = form.values()
    assert values["name"] == "a" and values["n"] == 3 and values["flag"] is True
    assert values["mode"] == "b" and values["files"] == ["x.txt"]

    # validation marks the folder (required, must exist) and clears again
    problems = form.validate()
    assert any("folder" in p for p in problems)
    assert editors["folder"].edit.property("invalid") is True
    unknown = form.set_values({"folder": str(tmp_path), "name": "", "nope": 1,
                               "files": ["a", "b"], "flag": False, "mode": "a"})
    assert unknown == ["nope"]
    problems = form.validate()
    assert problems == ["Name: required"]
    assert editors["folder"].edit.property("invalid") is False
    assert form.values()["files"] == ["a", "b"] and form.values()["flag"] is False
    form.reset_defaults()
    assert form.values()["name"] == "a" and form.values()["flag"] is True

    # presets live per flow family, "_last" separately
    fid = "family-1"
    presets.save_preset(fid, "Run A", {"name": "A"})
    presets.save_last(fid, {"name": "L"})
    assert presets.list_presets(fid) == ["Run A"]
    assert presets.load_preset(fid, "Run A") == {"name": "A"}
    assert presets.load_last(fid) == {"name": "L"}
    presets.delete_preset(fid, "Run A")
    assert presets.list_presets(fid) == []


async def test_form_page_runs_single_flow(tmp_path):
    from polytess.viewer.form_page import FormPage
    folder = _demo_copy(tmp_path)
    graph = Graph.load(str(folder / "prepare.flow.json"))
    page = FormPage(graph)
    assert page.stack.currentIndex() == 0
    page.form.set_values({"project_name": "t1", "work_folder": str(folder / "out")})
    page.workdir.setText(str(folder))
    page.start()
    assert page.is_running and page.stack.currentIndex() == 1
    await page._task
    await asyncio.sleep(0.05)
    assert not page.is_running
    assert page.stack.currentIndex() == 2                  # result view
    assert page.result_title.text().startswith("Finished")
    assert os.path.isfile(folder / "out" / "t1_model.txt")
    rows = {page.outputs.item(r, 0).text(): page.outputs.item(r, 1).text()
            for r in range(page.outputs.rowCount())}
    assert rows["Model file"].endswith("t1_model.txt")
    # last values were remembered for the next time
    from polytess.viewer import presets
    assert presets.load_last(graph.lineage.flow_id)["project_name"] == "t1"


async def test_board_page_runs_cards_with_auto_advance(tmp_path):
    from polytess.viewer.board_page import BoardPage
    folder = _demo_copy(tmp_path)
    graph = Graph.load(str(folder / "main_process.flow.json"))
    graph.variables.set("work_folder", str(folder / "work"))
    page = BoardPage(graph)
    spec = page.runner.spec
    assert len(page.view.items_by_guid) == 5
    columns = {c.title: page.view.items_by_guid[c.guid].status for c in spec.cards}
    assert set(columns.values()) == {PENDING}

    prep = spec.card_by_title("Prepare Model")
    page.auto_box.setChecked(True)
    page.start_card(prep.guid)
    assert page.is_running
    # wait until every card finished (auto-advance chains them)
    for _ in range(600):
        await asyncio.sleep(0.1)
        if not page.is_running and all(page.runner.status(c.guid) == DONE
                                       for c in spec.cards):
            break
    assert all(page.runner.status(c.guid) == DONE for c in spec.cards), \
        {c.title: page.runner.status(c.guid) for c in spec.cards}
    assert os.path.isfile(folder / "work" / "bracket_v1_report.txt")
    assert graph.variables.get("summary").startswith("bracket_v1")
    # view and dashboard follow the state
    assert all(item.status == DONE for item in page.view.items_by_guid.values())
    assert page.dashboard.ring._text == "5 / 5"
    # the board state is persisted next to the flow; reopening recognizes it
    page2 = BoardPage(Graph.load(str(folder / "main_process.flow.json")))
    assert all(page2.runner.status(c.guid) == DONE for c in page2.runner.spec.cards)
    # dropping a Done card on Backlog forgets it (and its successors)
    mesh = page2.runner.spec.card_by_title("Mesh")
    page2._dropped(mesh.guid, "backlog")
    assert page2.runner.status(mesh.guid) == PENDING
    assert page2.runner.status(page2.runner.spec.card_by_title("Report").guid) == PENDING
    assert page2.runner.status(page2.runner.spec.card_by_title("Prepare Model").guid) == DONE


def test_board_columns_stretch_with_the_view(tmp_path):
    from polytess.viewer.board_page import BoardPage
    from polytess.viewer.board_view import COL_W, COL_GAP, PAD, column_at
    folder = _demo_copy(tmp_path)
    page = BoardPage(Graph.load(str(folder / "main_process.flow.json")))
    view = page.view
    view.resize(1500, 600)
    view.relayout(animate=False)
    col_w = view.column_width
    assert col_w > COL_W + 100
    item = next(iter(view.items_by_guid.values()))
    assert abs(item.width - (col_w - 2 * PAD)) < 1
    assert view.sceneRect().width() == 3 * col_w + 2 * COL_GAP
    assert column_at(col_w * 1.5 + COL_GAP, col_w) == "active"
    assert column_at(col_w * 2.5 + 2 * COL_GAP, col_w) == "done"
    view.resize(500, 600)
    view.relayout(animate=False)
    assert view.column_width == COL_W                 # never narrower than the minimum

    # a slide that is still running must not drag a card back to its
    # old column position after a non-animated relayout (window resized
    # right after opening a finished process)
    AppSettings.instance().set("viewer_celebrations", "subtle")
    done_item = view.items_by_guid[page.runner.spec.card_by_title("Report").guid]
    view.set_status(done_item.card.guid, DONE)        # lives in the right column
    view.resize(1500, 600)
    view.relayout(animate=True)                       # its target moved -> slide runs
    assert done_item.property("_slide") is not None
    view.relayout(animate=False)
    assert all(i.property("_slide") is None and i.pos() == i._home
               for i in view.items_by_guid.values())


async def test_leaving_the_board_while_a_card_runs_detaches_callbacks(tmp_path):
    """Navigating away while a card runs: the page is deleted but the
    card task still winds down on the loop — it must not call into the
    (deleted) view any more (this crashed the process)."""
    from polytess.viewer.board_page import BoardPage
    folder = _demo_copy(tmp_path)
    graph = Graph.load(str(folder / "main_process.flow.json"))
    graph.variables.set("work_folder", str(folder / "work"))
    page = BoardPage(graph)
    page.auto_box.setChecked(False)
    prep = page.runner.spec.card_by_title("Prepare Model")
    page.start_card(prep.guid, mode="only")
    await asyncio.sleep(0.2)
    assert page.is_running
    runner, tasks = page.runner, list(page._tasks.values())
    page.detach()
    for guid in list(page._tasks):
        page.stop_card(guid)
    page.deleteLater()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()                # the C++ widgets are gone now
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert runner.on_change is None and runner.on_progress is None and runner.on_log is None
    assert runner.status(prep.guid) == PENDING  # cancelled run left no result


def test_board_theme_switch(tmp_path):
    from polytess.viewer.app import ViewerWindow
    from polytess.viewer.style import BOARD_THEMES
    folder = _demo_copy(tmp_path)
    window = ViewerWindow()
    window.open_flow(str(folder / "main_process.flow.json"))
    view = window._page.view
    assert view.theme is BOARD_THEMES["classic"]
    window.theme_box.setCurrentIndex(window.theme_box.findData("vivid"))
    assert AppSettings.instance().get("viewer_board_theme") == "vivid"
    assert view.theme is BOARD_THEMES["vivid"]
    assert all(i.theme is BOARD_THEMES["vivid"] for i in view.items_by_guid.values())
    assert set(BOARD_THEMES) == {"classic", "tinted", "headers", "cards", "vivid"}
    for theme in BOARD_THEMES.values():
        assert set(theme["column_body"]) == {"backlog", "active", "done"}


def test_viewer_window_routes_board_and_form(tmp_path):
    from polytess.viewer.app import ViewerWindow
    from polytess.viewer.board_page import BoardPage
    from polytess.viewer.form_page import FormPage
    folder = _demo_copy(tmp_path)
    window = ViewerWindow()
    window.open_flow(str(folder / "main_process.flow.json"))
    assert isinstance(window._page, BoardPage)
    window.open_flow(str(folder / "mesh.flow.json"))
    assert isinstance(window._page, FormPage)
    recent = AppSettings.instance().get("viewer_recent")
    assert recent[0].endswith("mesh.flow.json") and recent[1].endswith("main_process.flow.json")
    window.show_start()
    assert window.stack.currentWidget() is window.start_page
    assert window.start_page.recent.count() == 2
