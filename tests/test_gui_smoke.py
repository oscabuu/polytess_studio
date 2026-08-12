"""GUI smoke tests (offscreen): construct the main window, load the demo
workflow, drive scene/inspector/selector programmatically, run a workflow
through the Qt event loop."""

import asyncio
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import polytess.library  # noqa: F401,E402
from polytess.core import GlobalScope  # noqa: E402
from polytess.graph import ActionsNode, ConditionsNode, Graph, StartNode, TriggerNode  # noqa: E402

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "demo.flow.json")


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def fresh_globals():
    GlobalScope.reset()
    yield
    GlobalScope.reset()


def test_theme_and_icons(app):
    from polytess.gui.theme import build_qss
    from polytess.gui.icons import icon
    assert "QWidget" in build_qss()
    for name in ("play", "stop", "folder", "bolt", "drag", "chevron-down"):
        assert not icon(name).isNull()


def test_app_icon(app, tmp_path):
    from polytess.gui.app_icon import app_icon, export_png, render_pixmap
    icon_obj = app_icon()
    assert not icon_obj.isNull()
    assert len(icon_obj.availableSizes()) >= 5
    pixmap = render_pixmap(64)
    assert pixmap.width() == 64 and not pixmap.isNull()
    out = tmp_path / "icon.png"
    export_png(str(out), 128)
    assert out.exists() and out.stat().st_size > 1000


def test_scene_items_and_connect(app):
    from polytess.gui.graph.scene import GraphScene
    graph = Graph("t")
    graph.ensure_endpoints()
    scene = GraphScene(graph)
    assert len(scene.node_items) == 2

    scene.add_node_at(ActionsNode, QPointF(10, 20))
    assert len(scene.node_items) == 3
    scene.undo_stack.undo()
    assert len(scene.node_items) == 2
    scene.undo_stack.redo()
    assert len(scene.node_items) == 3

    start = next(iter(graph.nodes_of_type(StartNode)))
    actions = next(iter(graph.nodes_of_type(ActionsNode)))
    from polytess.gui.graph.commands import ConnectCommand
    scene.undo_stack.push(ConnectCommand(scene, start, "out", actions, "in"))
    assert len(graph.edges) == 1
    scene.undo_stack.undo()
    assert len(graph.edges) == 0


def test_node_item_geometry_and_ports(app):
    from polytess.gui.graph.scene import GraphScene
    graph = Graph("t")
    node = ConditionsNode()
    graph.add_node(node)
    scene = GraphScene(graph)
    item = scene.node_items[node.guid]
    # two horizontal out ports -> port rows
    assert len(item.port_rows) == 2
    success = node.port("success")
    fail = node.port("fail")
    assert item.port_pos(success).y() != item.port_pos(fail).y()
    hit = item.port_at(item.port_pos(success))
    assert hit is success


def test_copy_paste(app):
    from polytess.gui.graph.scene import GraphScene
    graph = Graph("t")
    graph.ensure_endpoints()
    a = graph.add_node(ActionsNode())
    scene = GraphScene(graph)
    scene.node_items[a.guid].setSelected(True)
    scene.copy_selection()
    scene.paste(QPointF(400, 400))
    assert len([n for n in graph.nodes if isinstance(n, ActionsNode)]) == 2
    guids = [n.guid for n in graph.nodes]
    assert len(set(guids)) == len(guids)


def test_group_wraps_selection_and_is_deletable(app):
    from PySide6.QtCore import QPointF as _QPointF
    from polytess.gui.graph.decorations import GroupItem
    from polytess.gui.graph.scene import GraphScene
    graph = Graph("t")
    a, b = graph.add_node(ActionsNode()), graph.add_node(ActionsNode())
    a.x, a.y = 0, 0
    b.x, b.y = 500, 300
    scene = GraphScene(graph)
    scene.node_items[a.guid].setSelected(True)
    scene.node_items[b.guid].setSelected(True)

    scene.add_group_at(_QPointF(0, 0))
    assert len(graph.groups) == 1
    group = graph.groups[0]
    # group frames BOTH selected nodes
    for node in (a, b):
        item = scene.node_items[node.guid]
        assert group.x <= node.x and group.y <= node.y
        assert node.x + item.width <= group.x + group.width
        assert node.y + item.height <= group.y + group.height

    # only the title bar is selectable, the body lets clicks through
    group_item = next(i for i in scene.items() if isinstance(i, GroupItem))
    assert group_item.shape().contains(_QPointF(group.width / 2, 10))
    assert not group_item.shape().contains(_QPointF(group.width / 2,
                                                    group.height / 2))

    # groups are deletable (undoably)
    scene.clearSelection()
    group_item = next(i for i in scene.items() if isinstance(i, GroupItem))
    group_item.setSelected(True)
    scene.delete_selection()
    assert len(graph.groups) == 0
    scene.undo_stack.undo()
    assert len(graph.groups) == 1


def test_blackboard_lists_panel(app):
    from PySide6.QtCore import Qt
    from polytess.gui.blackboard import SCALAR_TYPES, BlackboardPanel
    # "list" and "null" are no scalar variable types (lists live in Lists section)
    assert "list" not in SCALAR_TYPES and "null" not in SCALAR_TYPES
    assert "integer" in SCALAR_TYPES and "number" in SCALAR_TYPES

    graph = Graph("t")
    graph.lists.declare("cases", "string", ["a", "b"])
    graph.variables.declare("model", "path", "/tmp/model.inp")
    panel = BlackboardPanel()
    panel.set_graph(graph)

    tree = panel.graph_lists.tree
    assert tree.topLevelItemCount() == 1
    top = tree.topLevelItem(0)
    assert top.childCount() == 2
    assert top.child(1).text(1) == "b"

    # + element on selected list
    tree.setCurrentItem(top)
    panel.graph_lists._add_element()
    assert len(graph.lists.get("cases")) == 3

    # − removes the selected element
    top = tree.topLevelItem(0)
    tree.setCurrentItem(top.child(0))
    panel.graph_lists._remove_selected()
    assert graph.lists.get("cases").items[0] == "b"

    # element rows must be interactively editable (double-click editor)
    top = tree.topLevelItem(0)
    assert top.child(0).flags() & Qt.ItemIsEditable
    assert top.flags() & Qt.ItemIsEditable   # list rename

    # edit element value inline
    top.child(0).setText(1, "z")
    assert graph.lists.get("cases").items[0] == "z"

    # path variable renders with a PathEdit (browse button)
    from polytess.gui.widgets import PathEdit
    table = panel.graph_vars.table
    row = graph.variables.names().index("model")
    assert isinstance(table.cellWidget(row, 2), PathEdit)
    table.cellWidget(row, 2).setText("/tmp/other.inp")
    assert graph.variables.get("model") == "/tmp/other.inp"

    # − removes a whole list when the list itself is selected
    tree.setCurrentItem(tree.topLevelItem(0))
    panel.graph_lists._remove_selected()
    assert len(graph.lists) == 0

    # path lists: every element gets a PathEdit with browse button
    graph.lists.declare("decks", "path", ["/tmp/a.inp", "/tmp/b.inp"])
    top = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
               if tree.topLevelItem(i).data(0, Qt.UserRole) == "decks")
    editor = tree.itemWidget(top.child(0), 1)
    assert isinstance(editor, PathEdit)
    editor.setText("/tmp/c.inp")
    assert graph.lists.get("decks").items[0] == "/tmp/c.inp"
    assert graph.lists.get("decks").items[1] == "/tmp/b.inp"


def test_blackboard_table_variable_renders_compact_row(app):
    """Table variables show as ONE compact row: a summary plus an edit
    icon opening the spreadsheet dialog — not the full contents."""
    from polytess.gui.blackboard import BlackboardPanel
    from polytess.gui.widgets import TableSummaryEdit

    graph = Graph("t")
    graph.variables.declare("loads", "table", {
        "columns": ["deck", "load"],
        "rows": [{"deck": "MR_001", "load": 12},
                 {"deck": "MR_002", "load": 15}]})
    panel = BlackboardPanel()
    panel.set_graph(graph)

    table = panel.graph_vars.table
    row = graph.variables.names().index("loads")
    editor = table.cellWidget(row, 2)
    assert isinstance(editor, TableSummaryEdit)
    assert editor.summary.text()                 # e.g. "2 columns × 2 rows"
    assert editor.edit_button.toolTip()

    # an edited table (as the dialog would deliver it) propagates back
    edited = {"columns": ["deck", "load"],
              "rows": [{"deck": "MR_001", "load": 99}]}
    editor._table = edited
    editor._refresh()
    editor.changed.emit(edited)
    assert graph.variables.get("loads")["rows"][0]["load"] == 99


def test_inspector_tooltips_sit_on_bold_parameter_names(app):
    """FIELD_HELP lands as a tooltip on the (bold) parameter-name label
    only — value editors carry none, and a source's sub-rows explain
    the owning parameter, not the generic source mechanics."""
    from PySide6.QtWidgets import QLabel, QLineEdit
    from polytess.core.properties import GetGraphVariable
    from polytess.gui.inspector.fields import build_fields_widget
    from polytess.library.instructions.instruction_create_folder import \
        CreateFolder
    from polytess.library.instructions.instruction_run_command import \
        RunCommand

    widget = build_fields_widget(CreateFolder("x"), lambda: None)
    labels = [l for l in widget.findChildren(QLabel) if l.text() == "Path"]
    assert labels and "Directory to create" in labels[0].toolTip()
    assert labels[0].font().bold()
    # the nested constant-value row: label inherits the parameter help,
    # is not bold, and the editor itself has no tooltip
    value_labels = [l for l in widget.findChildren(QLabel)
                    if l.text() == "Value"]
    assert value_labels and "Directory to create" in value_labels[0].toolTip()
    assert not value_labels[0].font().bold()
    for editor in widget.findChildren(QLineEdit):
        assert editor.toolTip() == ""

    # variable-bound: the "Variable" row explains the parameter too
    block = CreateFolder()
    block.path = type(block.path)(GetGraphVariable("deck_dir"))
    widget = build_fields_widget(block, lambda: None)
    var_labels = [l for l in widget.findChildren(QLabel)
                  if l.text() == "Variable"]
    assert var_labels and "Directory to create" in var_labels[0].toolTip()

    # scalar fields: tooltip on the bold label only
    widget = build_fields_widget(RunCommand("echo 1"), lambda: None)
    labels = {l.text(): l for l in widget.findChildren(QLabel)}
    assert labels["Check Exit Code"].toolTip() != ""
    assert labels["Check Exit Code"].font().bold()


def test_table_summary_edit_roundtrip(app):
    from polytess.gui.widgets import TableSummaryEdit

    data = {"columns": ["a", "b"], "rows": [{"a": 1, "b": "x"}]}
    changes = []
    widget = TableSummaryEdit(data)
    widget.changed.connect(changes.append)
    assert widget.table() == data
    assert not changes                     # loading emits nothing
    assert widget.summary.text()           # compact one-line summary


def test_blackboard_variable_groups(app):
    """Variables can be grouped (collapsible header rows); moving a
    variable between groups is metadata-only, and renames rewrite the
    references in the current graph."""
    from PySide6.QtCore import Qt
    from polytess.core.refs import find_references
    from polytess.graph.flow_builder import build_flow
    from polytess.gui.blackboard import BlackboardPanel

    graph = build_flow({
        "name": "groups",
        "variables": [{"name": "deck", "type": "string", "value": "MR_001"},
                      {"name": "speed", "type": "number", "value": 1}],
        "nodes": [{"id": "a", "kind": "actions", "instructions": [
            {"type": "LogMessage",
             "params": {"message": {"template": "Deck {deck}"}}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph
    panel = BlackboardPanel()
    panel.set_graph(graph)
    table_widget = panel.graph_vars

    # move 'deck' into a group -> a bold header row appears
    table_widget._set_group("deck", "Inputs")
    assert graph.variables.variable("deck").group == "Inputs"
    headers = [table_widget.table.item(r, 0).text()
               for r in range(table_widget.table.rowCount())
               if table_widget.table.item(r, 0) is not None
               and table_widget.table.item(r, 0).data(
                   table_widget._GROUP_ROLE) is not None]
    assert headers and "Inputs" in headers[0]

    # references are untouched by grouping
    assert find_references(graph, "deck")

    # collapse hides the member row
    def variable_rows():
        return [r for r in range(table_widget.table.rowCount())
                if table_widget.table.item(r, 0) is not None
                and table_widget.table.item(r, 0).data(Qt.UserRole)]
    rows_before = len(variable_rows())
    header_row = next(r for r in range(table_widget.table.rowCount())
                      if table_widget.table.item(r, 0).data(
                          table_widget._GROUP_ROLE) is not None)
    table_widget._on_cell_clicked(header_row, 0)
    assert len(variable_rows()) == rows_before - 1

    # moving out again works and keeps references
    table_widget._set_group("deck", "")
    assert graph.variables.variable("deck").group == ""
    assert find_references(graph, "deck")

    # renaming via the blackboard rewrites graph references
    table_widget._updating = True
    graph.variables.rename("deck", "deck_id")
    table_widget._updating = False
    table_widget._rename_references("deck", "deck_id")
    assert not find_references(graph, "deck")
    assert find_references(graph, "deck_id")

    # group rename moves every member (and keeps the collapse state key)
    table_widget._set_group("deck_id", "Inputs")
    table_widget._set_group("speed", "Inputs")
    table_widget._collapsed.add("Inputs")
    table_widget._apply_group_rename("Inputs", "Model Inputs")
    assert graph.variables.variable("deck_id").group == "Model Inputs"
    assert graph.variables.variable("speed").group == "Model Inputs"
    assert "Model Inputs" in table_widget._collapsed

    # delete dissolves the group: members move out, variables survive
    table_widget._delete_group("Model Inputs")
    assert graph.variables.variable("deck_id").group == ""
    assert graph.variables.variable("speed").group == ""
    assert graph.variables.exists("deck_id") and graph.variables.exists("speed")
    assert "Model Inputs" not in table_widget._collapsed
    assert not table_widget._group_names()


def test_bool_variables_use_selection_menu(app):
    """Bool values are edited via a True/False selection menu — in the
    variables table, in bool lists and in the New Variable dialog."""
    from PySide6.QtCore import Qt
    from polytess.gui.blackboard import BlackboardPanel, _NewVariableDialog
    from polytess.gui.widgets import BoolCombo

    graph = Graph("t")
    graph.variables.declare("flag", "bool", True)
    graph.lists.declare("flags", "bool", [True, False])
    panel = BlackboardPanel()
    panel.set_graph(graph)

    # variables table: combo instead of an editable "True" string
    table = panel.graph_vars.table
    row = graph.variables.names().index("flag")
    editor = table.cellWidget(row, 2)
    assert isinstance(editor, BoolCombo)
    assert editor.value() is True
    editor.setCurrentIndex(1)                  # pick "False"
    assert graph.variables.get("flag") is False

    # bool list elements: combo per element
    tree = panel.graph_lists.tree
    top = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
               if tree.topLevelItem(i).data(0, Qt.UserRole) == "flags")
    element = tree.itemWidget(top.child(1), 1)
    assert isinstance(element, BoolCombo)
    element.setCurrentIndex(0)                 # pick "True"
    assert graph.lists.get("flags").items[1] is True

    # dialog: value field swaps to the selection menu for bool
    dialog = _NewVariableDialog()
    assert dialog.value_edit.isVisibleTo(dialog)
    dialog.type_combo.setCurrentText("bool")
    assert not dialog.value_edit.isVisibleTo(dialog)
    assert dialog.value_bool.isVisibleTo(dialog)
    dialog.value_bool.setCurrentIndex(1)
    assert dialog.value() is False


def test_blackboard_search_sort_filter(app):
    from polytess.gui.blackboard import BlackboardPanel
    graph = Graph("t")
    graph.variables.declare("zeta", "number", 1)
    graph.variables.declare("alpha", "string", "hello")
    graph.variables.declare("count", "integer", 3)
    panel = BlackboardPanel()
    panel.set_graph(graph)
    table_widget = panel.graph_vars

    # type icons present on every name cell
    assert not table_widget.table.item(0, 0).icon().isNull()

    # sort by name (ascending / descending / back to insertion order)
    table_widget._sort_by(0)
    assert [table_widget.table.item(r, 0).text() for r in range(3)] == \
        ["alpha", "count", "zeta"]
    table_widget._sort_by(0)
    assert table_widget.table.item(0, 0).text() == "zeta"
    table_widget._sort_by(0)
    assert table_widget.table.item(0, 0).text() == "zeta"   # insertion order
    # sort by type groups equal types
    table_widget._sort_by(1)
    assert [table_widget.table.item(r, 1).text() for r in range(3)] == \
        ["integer", "number", "string"]
    table_widget._sort_by(1); table_widget._sort_by(1)      # reset

    # search matches names and values
    table_widget.header_bar.search.setText("alp")
    assert table_widget.table.rowCount() == 1
    assert table_widget.table.item(0, 0).text() == "alpha"
    table_widget.header_bar.search.setText("hello")         # value match
    assert table_widget.table.rowCount() == 1
    table_widget.header_bar.search.setText("")
    assert table_widget.table.rowCount() == 3

    # type filter
    table_widget.header_bar._filter_types = {"integer"}
    table_widget.refresh()
    assert table_widget.table.rowCount() == 1
    assert table_widget.table.item(0, 0).text() == "count"
    table_widget.header_bar._filter_types = set()
    table_widget.refresh()

    # editing still targets the right variable while sorted
    table_widget._sort_by(0)   # alpha first
    table_widget.table.item(0, 2).setText("changed")
    assert graph.variables.get("alpha") == "changed"


def test_template_edit_widget(app):
    from polytess.core.properties import GetPathFormat
    from polytess.gui.inspector.fields import build_fields_widget
    from polytess.gui.widgets import TemplateEdit

    graph = Graph("t")
    graph.variables.declare("case", "string", "demo01")

    editor = TemplateEdit("out/{case}/result", graph)
    assert editor.preview.isVisibleTo(editor)
    assert "out/demo01/result" in editor.preview.text()
    editor.insert_placeholder("case")
    assert editor.text().endswith("{case}")

    # fields builder uses TemplateEdit for 'template' attributes
    source = GetPathFormat("runs/{case}")
    changes = []
    widget = build_fields_widget(source, lambda: changes.append(1), graph=graph)
    template_edits = widget.findChildren(TemplateEdit)
    assert len(template_edits) == 1
    template_edits[0].setText("neu/{case}")
    assert source.template == "neu/{case}"
    assert changes


def test_references_dialog(app):
    from polytess.core.refs import Reference, find_references
    from polytess.gui.refs_dialog import ReferencesDialog
    from polytess.core.properties import (GetGraphVariable, PropertyGetString,
                                        PropertySetString, SetGraphVariable)
    from polytess.library.instructions.instruction_set_string import SetString

    graph = Graph("t")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    inst = SetString()
    inst.target = PropertySetString(SetGraphVariable("case"))
    inst.value = PropertyGetString(GetGraphVariable("case"))
    node.instructions.instructions.append(inst)

    references = find_references(graph, "case", "graph")
    assert len(references) == 2
    picked = []
    dialog = ReferencesDialog("case", "graph", references,
                              on_goto=picked.append)
    assert dialog.table.rowCount() == 2
    dialog._goto(dialog.table.item(0, 1))
    assert picked == [node.guid]
    dialog.close()


def test_pause_step_actions_exist(app):
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from polytess.gui.main_window import MainWindow
    window = MainWindow()
    assert not window.act_pause.isEnabled()      # only while running
    assert not window.act_step.isEnabled()
    assert window.act_pause.isCheckable()
    # breakpoint toggle on the scene
    doc = window.current_document()
    node = doc.graph.nodes[0].__class__          # StartNode exists
    a = doc.scene.graph.add_node(ActionsNode())
    doc.scene.sync_items()
    doc.scene.node_items[a.guid].setSelected(True)
    doc.scene.toggle_breakpoints()
    assert a.breakpoint is True
    doc.scene.toggle_breakpoints()
    assert a.breakpoint is False
    window.tabs.clear()


def test_type_selector_search(app):
    from polytess.core.instructions import Instruction
    from polytess.core.metadata import iter_subclasses
    from polytess.gui.type_selector import TypeSelectorPopup, _search
    candidates = list(iter_subclasses(Instruction))
    hits = _search(candidates, "folder")
    from polytess.library.instructions.instruction_create_folder import CreateFolder
    assert CreateFolder in hits
    popup = TypeSelectorPopup(candidates, lambda cls: None)
    popup.search.setText("create folder")
    assert popup.listing.count() > 0
    popup.close()


def test_inspector_builds_for_all_node_types(app):
    from polytess.gui.inspector.inspector import InspectorPanel
    from polytess.graph.nodes import (ActionsNode, BranchNode, ConditionsNode,
                                    ExitNode, StartNode, SubGraphNode, TriggerNode)
    from polytess.library.events.event_on_start import OnStart
    from polytess.library.instructions.instruction_log_message import LogMessage
    graph = Graph("t")
    graph.ensure_endpoints()
    panel = InspectorPanel()
    for node_cls in (ActionsNode, ConditionsNode, BranchNode, TriggerNode, SubGraphNode):
        node = graph.add_node(node_cls())
        if isinstance(node, TriggerNode):
            node.event = OnStart()
        if isinstance(node, ActionsNode):
            node.instructions.instructions.append(LogMessage("hi"))
        panel.set_node(node, graph)
    panel.set_node(next(iter(graph.nodes_of_type(StartNode))), graph)
    panel.set_node(next(iter(graph.nodes_of_type(ExitNode))), graph)
    panel.set_node(None, None)


def test_poly_list_widget_edit_ops(app):
    from polytess.core.instructions import Instruction
    from polytess.gui.inspector.poly_list import PolymorphicListWidget
    from polytess.library.instructions.instruction_log_message import LogMessage
    from polytess.library.instructions.instruction_wait_seconds import WaitSeconds
    items = [LogMessage("a"), WaitSeconds(1.0)]
    widget = PolymorphicListWidget("Instructions", Instruction, items)
    assert len(widget._rows) == 2
    widget.duplicate_item(0)
    assert len(items) == 3 and isinstance(items[1], LogMessage)
    widget.delete_item(1)
    assert len(items) == 2
    widget.insert_item(0, WaitSeconds(2.0))
    assert isinstance(items[0], WaitSeconds)
    # title rendering
    assert "Wait" in widget._rows[0].title_label.text()


def test_flow_assistant_dock_tabbed_and_closable(app):
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from PySide6.QtWidgets import QDockWidget, QMainWindow
    from polytess.gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    # docks can be tabbed and arranged side by side
    assert window.dockOptions() & QMainWindow.AllowTabbedDocks
    assert window.dockOptions() & QMainWindow.AllowNestedDocks
    assert window.isDockNestingEnabled()

    window._open_flow_assistant()
    dock = window.dock_flow_assistant
    # closable via the title-bar X …
    assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable
    dock.close()
    assert not dock.isVisible()
    # … and re-openable via the View menu toggle
    toggles = [a for a in window._view_menu.actions()
               if a.text() == "Flow Assistant"]
    assert toggles and toggles[0].isCheckable()
    toggles[0].trigger()
    assert dock.isVisible()
    # docked as a tab next to the Inspector
    assert dock in window.tabifiedDockWidgets(window.dock_inspector) \
        or window.dock_inspector in window.tabifiedDockWidgets(dock)
    window.close()


def test_assistant_modification_creates_branch(app, tmp_path):
    """Inserting an assistant answer that modified the open flow creates
    a lineage branch of it — an unrelated build stays independent."""
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from polytess.graph.flow_builder import build_flow
    from polytess.gui.main_window import GraphDocument, MainWindow

    window = MainWindow()
    source_graph = build_flow({
        "name": "Source", "nodes": [
            {"id": "a", "kind": "actions", "instructions": [
                {"type": "LogMessage", "params": {"message": "hi"}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph
    path = str(tmp_path / "source.flow.json")
    source_graph.save(path)
    doc = window.open_document(path)
    base = doc.graph.lineage

    modified = build_flow({
        "name": "Source", "nodes": [
            {"id": "a", "kind": "actions", "instructions": [
                {"type": "LogMessage", "params": {"message": "hi"}},
                {"type": "LogMessage", "params": {"message": "more"}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph
    window._open_built_graph(modified, True)

    branched = window.current_document()
    lineage = branched.graph.lineage
    assert lineage.flow_id == base.flow_id           # same family
    assert lineage.branch == "assistant"
    assert lineage.parent_branch == base.branch
    assert (tmp_path / "source@assistant.flow.json").is_file()

    # an unrelated (from-scratch) flow keeps its own fresh lineage
    fresh = build_flow({"name": "Fresh", "nodes": [], "edges": []}).graph
    window._open_built_graph(fresh, False)
    assert window.current_document().graph.lineage.flow_id != base.flow_id
    window.close()


def test_flow_assistant_insert_reports_context_flag(app):
    from polytess.gui.flow_assistant import FlowAssistantPanel

    panel = FlowAssistantPanel()
    received = []
    panel.open_graph.connect(
        lambda graph, from_context: received.append(from_context))
    panel._last_flow = {"name": "X", "nodes": [], "edges": []}

    panel._answer_from_context = False
    panel._insert_flow()
    panel._answer_from_context = True
    panel._insert_flow()
    assert received == [False, True]


def test_f4_toggles_live_value_display(app):
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from polytess.core.properties import live_display_enabled
    from polytess.graph.flow_builder import build_flow
    from polytess.gui.main_window import GraphDocument, MainWindow

    window = MainWindow()
    graph = build_flow({
        "name": "live", "variables": [
            {"name": "result_dir", "type": "path", "value": "/proj/runs"}],
        "nodes": [{"id": "a", "kind": "actions", "instructions": [
            {"type": "CreateFolder", "params": {"path": {"var": "result_dir"}}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph
    window._add_document(GraphDocument(graph))
    node = next(n for n in graph.nodes if n.name == "Actions")
    instruction = list(node.instructions)[0]

    assert window.act_live_values.shortcut().toString() == "F4"
    assert "graph:result_dir" in instruction.title

    window.act_live_values.setChecked(True)
    assert live_display_enabled()
    assert "/proj/runs" in instruction.title

    window.act_live_values.setChecked(False)
    assert not live_display_enabled()
    assert "graph:result_dir" in instruction.title
    window.close()


def test_main_window_open_and_run(app, tmp_path):
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from polytess.gui.main_window import MainWindow

    window = MainWindow()
    doc = window.open_document(os.path.abspath(EXAMPLE))
    assert doc is not None
    assert len(doc.graph.nodes) == 6

    # run the demo workflow through the qasync loop
    window.run_current()
    assert doc.is_running

    async def wait_done():
        while doc.is_running:
            await asyncio.sleep(0.05)

    loop.run_until_complete(asyncio.wait_for(wait_done(), timeout=15))
    assert doc.graph.variables.get("status") == "ok"
    # log received output
    assert any("Result file written" in text for _s, _l, text in window.log._entries)
    window.tabs.clear()
    # cleanup example output
    import shutil
    out_dir = os.path.join(os.path.dirname(os.path.abspath(EXAMPLE)), "out")
    shutil.rmtree(out_dir, ignore_errors=True)


def test_field_edit_is_undoable_and_merges(app):
    from PySide6.QtGui import QUndoStack
    from PySide6.QtWidgets import QDoubleSpinBox
    from polytess.gui.inspector.inspector import InspectorPanel
    from polytess.library.instructions.instruction_wait_seconds import WaitSeconds

    graph = Graph("t")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    inst = WaitSeconds(1.0)
    inst._ui_expanded = True
    node.instructions.instructions.append(inst)

    panel = InspectorPanel()
    stack = QUndoStack()
    panel.undo_stack = stack
    panel.set_node(node, graph)

    spin = panel.findChildren(QDoubleSpinBox)[0]
    # three rapid edits (like typing/scrubbing) merge into one undo step
    spin.setValue(2.0)
    spin.setValue(3.0)
    spin.setValue(4.0)
    assert inst.seconds.source.value == 4.0
    assert stack.count() == 1

    stack.undo()
    assert inst.seconds.source.value == 1.0
    # undo rebuilt the inspector (refresh_if_showing) — the old widget is
    # gone, re-query to confirm the field widget itself picked it up too
    assert panel.findChildren(QDoubleSpinBox)[0].value() == 1.0

    stack.redo()
    assert inst.seconds.source.value == 4.0


def test_node_header_field_is_undoable(app):
    from PySide6.QtGui import QUndoStack
    from PySide6.QtWidgets import QCheckBox
    from polytess.gui.inspector.inspector import InspectorPanel

    graph = Graph("t")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    assert node.enabled is True

    panel = InspectorPanel()
    stack = QUndoStack()
    panel.undo_stack = stack
    panel.set_node(node, graph)

    enabled_box = next(cb for cb in panel.findChildren(QCheckBox)
                       if cb.text() == "Enabled")
    enabled_box.setChecked(False)
    assert node.enabled is False
    assert stack.count() == 1

    stack.undo()
    assert node.enabled is True
    stack.redo()
    assert node.enabled is False


def test_poly_list_structural_edits_are_undoable(app):
    from PySide6.QtGui import QUndoStack
    from polytess.gui.inspector.inspector import InspectorPanel
    from polytess.gui.inspector.poly_list import PolymorphicListWidget
    from polytess.library.instructions.instruction_log_message import LogMessage
    from polytess.library.instructions.instruction_wait_seconds import WaitSeconds

    graph = Graph("t")
    graph.ensure_endpoints()
    node = graph.add_node(ActionsNode())
    node.instructions.instructions.append(LogMessage("a"))
    node.instructions.instructions.append(WaitSeconds(1.0))
    items = node.instructions.instructions

    panel = InspectorPanel()
    stack = QUndoStack()
    panel.undo_stack = stack
    panel.set_node(node, graph)

    list_widget = panel.findChild(PolymorphicListWidget)
    list_widget.duplicate_item(0)
    assert len(items) == 3 and isinstance(items[1], LogMessage)
    assert stack.count() == 1

    stack.undo()
    assert len(node.instructions.instructions) == 2
    stack.redo()
    assert len(node.instructions.instructions) == 3

    # delete and reorder are separate undo steps (not merged with each other)
    list_widget = panel.findChild(PolymorphicListWidget)
    list_widget.delete_item(0)
    assert len(node.instructions.instructions) == 2
    assert stack.count() == 2
    stack.undo()
    assert len(node.instructions.instructions) == 3


def test_settings_dialog_python_include_paths_roundtrip(app, tmp_path):
    from polytess.core.app_settings import AppSettings
    from polytess.gui.settings_dialog import SettingsDialog

    AppSettings.reset(path=str(tmp_path / "settings.json"))
    dialog = SettingsDialog()
    assert dialog.python_include_paths.values() == []

    dialog.python_include_paths._items = ["/a/b", " ", "/c/d"]
    dialog.python_include_paths._rebuild()
    dialog._save()

    settings = AppSettings.instance()
    # blank rows are dropped, real ones kept in order
    assert settings.get("python_include_paths") == ["/a/b", "/c/d"]
    assert "/a/b" in sys.path and "/c/d" in sys.path

    # cleanup: don't leak into other tests
    from polytess.core.app_settings import sync_python_include_paths
    AppSettings.reset(path="", python_include_paths=[])
    sync_python_include_paths()


def test_inspector_undo_stack_follows_active_tab(app):
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    from polytess.gui.main_window import MainWindow

    window = MainWindow()
    doc1 = window.current_document()
    assert window.inspector.undo_stack is doc1.scene.undo_stack

    doc2 = window.new_document()
    assert window.inspector.undo_stack is doc2.scene.undo_stack

    window.tabs.setCurrentWidget(doc1)
    assert window.inspector.undo_stack is doc1.scene.undo_stack
    window.tabs.clear()
