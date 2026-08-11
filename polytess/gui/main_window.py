# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Main window — the studio shell: menu bar, toolbar, graph tabs,
inspector/blackboard/log docks, run control with live highlighting."""

from __future__ import annotations

import asyncio
import os

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence, QUndoGroup
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog,
                               QMainWindow, QMessageBox, QTabWidget, QWidget)

from polytess.core.context import Context
from polytess.graph.model import Graph
from polytess.graph.processor import GraphProcessor, NodeStatus
from polytess.gui.blackboard import BlackboardPanel
from polytess.gui.graph.scene import GraphScene
from polytess.gui.graph.view import GraphView
from polytess.gui.icons import icon
from polytess.gui.inspector.inspector import InspectorPanel
from polytess.gui.log import LogPanel

MAX_RECENT = 8


class GraphDocument(QWidget):
    """One open workflow: model + scene + view + dirty state."""

    def __init__(self, graph: Graph, path: str = "", parent=None):
        super().__init__(parent)
        self.graph = graph
        self.path = path
        self.dirty = False
        self.processor: GraphProcessor | None = None
        self.run_task: asyncio.Task | None = None
        self.run_ctx: Context | None = None

        self.scene = GraphScene(graph)
        self.view = GraphView(self.scene)
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    @property
    def title(self) -> str:
        base = os.path.basename(self.path) if self.path else "untitled"
        base = base.replace(Graph.FILE_SUFFIX, "")
        return f"{base}{' •' if self.dirty else ''}"

    @property
    def is_running(self) -> bool:
        return self.run_task is not None and not self.run_task.done()


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        from polytess import __version__
        self.setWindowTitle(f"polytess Studio {__version__}")
        self.resize(1500, 950)
        self.settings = QSettings("polytess", "studio")

        self.undo_group = QUndoGroup(self)

        # central tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self.tabs)

        # docks may be closed, stacked as tabs (drag one onto another)
        # and arranged side by side within one dock area
        self.setDockOptions(QMainWindow.AnimatedDocks
                            | QMainWindow.AllowTabbedDocks
                            | QMainWindow.AllowNestedDocks)
        self.setDockNestingEnabled(True)

        # docks
        self.inspector = InspectorPanel()
        self.inspector.node_changed.connect(self._on_node_edited)
        self.inspector.graph_changed.connect(self._on_graph_edited)
        self.inspector.open_subgraph.connect(self._open_subgraph)
        self._add_dock("Inspector", self.inspector, Qt.RightDockWidgetArea,
                       min_width=360)

        self.blackboard = BlackboardPanel()
        self.blackboard.changed.connect(self._on_graph_edited)
        self.blackboard.find_references.connect(self._show_references)
        self._add_dock("Variables", self.blackboard, Qt.LeftDockWidgetArea,
                       min_width=260)

        self.log = LogPanel()
        self._add_dock("Log", self.log, Qt.BottomDockWidgetArea)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

        # snapshot of the as-built layout, before any saved state is
        # restored — lets "Restore Default Layout" put docks/toolbar back
        self._default_dock_state = self.saveState()

        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.settings.value("window/state")
        if state is not None:
            self.restoreState(state)

        self.new_document()

    # ---- docks -------------------------------------------------------------- #

    def _add_dock(self, title: str, widget, area, min_width: int = 0) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock-{title.lower()}")
        dock.setWidget(widget)
        if min_width:
            widget.setMinimumWidth(min_width)
        self.addDockWidget(area, dock)
        setattr(self, f"dock_{title.lower().replace(' ', '_')}", dock)
        return dock

    # ---- actions / menus ------------------------------------------------------ #

    def _build_actions(self) -> None:
        self.act_new = QAction(icon("file", "text"), "&New", self,
                               shortcut=QKeySequence.New, triggered=self.new_document)
        self.act_open = QAction(icon("folder", "text"), "&Open…", self,
                                shortcut=QKeySequence.Open, triggered=self._open_dialog)
        self.act_save = QAction(icon("save", "text"), "&Save", self,
                                shortcut=QKeySequence.Save, triggered=self.save_document)
        self.act_save_as = QAction("Save &As…", self,
                                   shortcut=QKeySequence.SaveAs,
                                   triggered=lambda: self.save_document(save_as=True))
        self.act_undo = self.undo_group.createUndoAction(self, "&Undo")
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setIcon(icon("undo", "text"))
        self.act_redo = self.undo_group.createRedoAction(self, "&Redo")
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.setIcon(icon("redo", "text"))
        self.act_run = QAction(icon("play", "green"), "&Run", self,
                               shortcut="F5", triggered=self.run_current)
        self.act_pause = QAction(icon("pause", "yellow"), "&Pause", self,
                                 shortcut="F6", checkable=True,
                                 triggered=self.pause_current)
        self.act_pause.setEnabled(False)
        self.act_step = QAction(icon("step", "yellow"), "Step &Forward", self,
                                shortcut="F7", triggered=self.step_current)
        self.act_step.setEnabled(False)
        self.act_stop = QAction(icon("stop", "red"), "S&top", self,
                                shortcut="Shift+F5", triggered=self.stop_current)
        self.act_stop.setEnabled(False)
        self.act_validate = QAction("&Validate", self, triggered=self.validate_current)
        self.act_fit = QAction(icon("zoom-fit", "text"), "Zoom to &Fit", self,
                               shortcut="F", triggered=self._zoom_fit)
        self.act_minimap = QAction(icon("minimap", "text"), "&Minimap", self,
                                   checkable=True, checked=True,
                                   triggered=self._toggle_minimap)
        self.act_restore_layout = QAction("&Restore Default Layout", self,
                                          triggered=self._restore_default_layout)
        self.act_add_node = QAction(icon("plus", "text"), "&Add Node…", self,
                                    shortcut="Ctrl+Space", triggered=self._add_node)
        self.act_settings = QAction(icon("gear", "text"), "S&ettings…", self,
                                    triggered=self._open_settings)
        self.act_code_editor = QAction(icon("edit", "text"), "&Code Editor", self,
                                       shortcut="Ctrl+E",
                                       triggered=self._open_code_editor)
        self.act_flow_assistant = QAction(icon("graph", "text"),
                                          "&Flow Assistant", self,
                                          shortcut="Ctrl+Shift+F",
                                          triggered=self._open_flow_assistant)
        self.act_about = QAction("&About polytess…", self,
                                 triggered=self._show_about)
        self.act_manual = QAction("polytess &Manual", self, shortcut="F1",
                                  triggered=self._open_manual)
        self.act_license = QAction("Commercial &License…", self,
                                   triggered=self._open_license)
        self.act_new_example = QAction("New from &Example…", self,
                                       triggered=self._new_from_example)
        self.act_branch = QAction(icon("branch", "text"), "Create &Branch…",
                                  self, shortcut="Ctrl+B",
                                  triggered=self._branch_current)
        self.act_compare = QAction("Co&mpare with Parent", self,
                                   shortcut="Ctrl+D",
                                   triggered=self._compare_current)
        self.act_promote = QAction("Promo&te to Parent…", self,
                                   triggered=self._promote_current)
        self.act_history = QAction("Flow &History…", self,
                                   triggered=self._history_current)
        self.act_export_doc = QAction(icon("file", "text"),
                                      "Export &Documentation…", self,
                                      triggered=self._export_documentation)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_new_example)
        file_menu.addAction(self.act_open)
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export_doc)
        file_menu.addSeparator()
        file_menu.addAction(self.act_settings)
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Quit", self, shortcut=QKeySequence.Quit,
                                    triggered=self.close))

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_add_node)

        library_menu = self.menuBar().addMenu("&Library")
        library_menu.addAction(self.act_code_editor)
        library_menu.addAction(self.act_flow_assistant)

        graph_menu = self.menuBar().addMenu("&Graph")
        graph_menu.addAction(self.act_run)
        graph_menu.addAction(self.act_pause)
        graph_menu.addAction(self.act_step)
        graph_menu.addAction(self.act_stop)
        graph_menu.addSeparator()
        graph_menu.addAction(self.act_validate)
        graph_menu.addSeparator()
        graph_menu.addAction(self.act_branch)
        graph_menu.addAction(self.act_compare)
        graph_menu.addAction(self.act_promote)
        graph_menu.addAction(self.act_history)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.act_fit)
        view_menu.addAction(self.act_minimap)
        view_menu.addSeparator()
        self._dock_toggle_separator = view_menu.addSeparator()
        for dock_name in ("inspector", "variables", "log"):
            dock = getattr(self, f"dock_{dock_name}", None)
            if dock is not None:
                view_menu.insertAction(self._dock_toggle_separator,
                                       dock.toggleViewAction())
        view_menu.addAction(self.act_restore_layout)
        self._view_menu = view_menu

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.act_manual)
        help_menu.addSeparator()
        help_menu.addAction(self.act_license)
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main-toolbar")
        toolbar.setMovable(False)
        # explicit size instead of the platform default — the vector icons
        # render exactly this size (and 2x on retina), nothing gets rescaled
        from PySide6.QtCore import QSize
        toolbar.setIconSize(QSize(20, 20))
        for action in (self.act_new, self.act_open, self.act_save, None,
                       self.act_undo, self.act_redo, None,
                       self.act_run, self.act_pause, self.act_step,
                       self.act_stop, None,
                       self.act_add_node, self.act_fit, self.act_minimap, None,
                       self.act_code_editor, self.act_flow_assistant,
                       self.act_settings):
            if action is None:
                toolbar.addSeparator()
            else:
                toolbar.addAction(action)

    # ---- documents ----------------------------------------------------------------- #

    def current_document(self) -> GraphDocument | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, GraphDocument) else None

    def new_document(self) -> GraphDocument:
        graph = Graph("Workflow")
        graph.ensure_endpoints()
        return self._add_document(GraphDocument(graph))

    def open_document(self, path: str) -> GraphDocument | None:
        path = os.path.abspath(path)
        for index in range(self.tabs.count()):
            doc = self.tabs.widget(index)
            if isinstance(doc, GraphDocument) and doc.path == path:
                self.tabs.setCurrentIndex(index)
                return doc
        try:
            graph = Graph.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"{path}\n\n{exc}")
            return None
        graph.ensure_endpoints()
        doc = self._add_document(GraphDocument(graph, path))
        self._push_recent(path)
        return doc

    def _add_document(self, doc: GraphDocument) -> GraphDocument:
        self.undo_group.addStack(doc.scene.undo_stack)
        doc.scene.selection_node_changed.connect(self._on_selection)
        doc.scene.modified.connect(lambda d=doc: self._mark_dirty(d))
        doc.scene.request_open_subgraph.connect(self._open_subgraph)
        doc.scene.undo_stack.indexChanged.connect(lambda _i, d=doc: self._mark_dirty(d))
        index = self.tabs.addTab(doc, doc.title)
        self.tabs.setCurrentIndex(index)
        doc.dirty = False
        self._refresh_tab_title(doc)
        return doc

    def _mark_dirty(self, doc: GraphDocument) -> None:
        doc.dirty = True
        self._refresh_tab_title(doc)

    def _refresh_tab_title(self, doc: GraphDocument) -> None:
        index = self.tabs.indexOf(doc)
        if index >= 0:
            self.tabs.setTabText(index, doc.title)
        if doc is self.current_document():
            from polytess import __version__
            self.setWindowTitle(f"polytess Studio {__version__} — {doc.title}")

    def _on_tab_changed(self, _index: int) -> None:
        doc = self.current_document()
        if doc is None:
            self.inspector.set_node(None, None)
            self.inspector.undo_stack = None
            self.blackboard.set_graph(None)
            return
        self.undo_group.setActiveStack(doc.scene.undo_stack)
        self.inspector.undo_stack = doc.scene.undo_stack
        self.blackboard.set_graph(doc.graph)
        self.inspector.set_node(None, None)
        self._refresh_tab_title(doc)
        self.act_stop.setEnabled(doc.is_running)
        self.act_run.setEnabled(not doc.is_running)
        self.act_pause.setEnabled(doc.is_running)
        self.act_pause.setChecked(doc.processor.is_paused
                                  if doc.processor is not None else False)
        self.act_step.setEnabled(doc.is_running)

    def _close_tab(self, index: int) -> None:
        doc = self.tabs.widget(index)
        from polytess.gui.code_editor import CodeEditorPanel
        if isinstance(doc, CodeEditorPanel):
            if doc.dirty:
                answer = QMessageBox.question(
                    self, "Unsaved changes", "Save the edited library file?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                if answer == QMessageBox.Cancel:
                    return
                if answer == QMessageBox.Save and not doc.save():
                    return
            self.tabs.removeTab(index)
            doc.deleteLater()
            return
        if not isinstance(doc, GraphDocument):
            return
        if doc.is_running:
            QMessageBox.information(self, "Running",
                                    "Stop the workflow before closing the tab.")
            return
        if doc.dirty:
            answer = QMessageBox.question(
                self, "Unsaved changes",
                f"Save changes to {doc.title.rstrip(' •')}?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Save:
                self.tabs.setCurrentIndex(index)
                if not self.save_document():
                    return
        self.undo_group.removeStack(doc.scene.undo_stack)
        self.tabs.removeTab(index)
        doc.deleteLater()

    # ---- file ops --------------------------------------------------------------------- #

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open workflow", self.settings.value("last-dir", ""),
            f"Workflows (*{Graph.FILE_SUFFIX});;All files (*)")
        if path:
            self.settings.setValue("last-dir", os.path.dirname(path))
            self.open_document(path)

    def save_document(self, save_as: bool = False) -> bool:
        from polytess.gui.code_editor import CodeEditorPanel
        active = self.tabs.currentWidget()
        if isinstance(active, CodeEditorPanel):
            return active.save()           # Ctrl+S in the editor tab
        doc = self.current_document()
        if doc is None:
            return False
        path = doc.path
        if save_as or not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save workflow",
                doc.path or self.settings.value("last-dir", ""),
                f"Workflows (*{Graph.FILE_SUFFIX})")
            if not path:
                return False
            if not path.endswith(Graph.FILE_SUFFIX):
                path += Graph.FILE_SUFFIX
            self.settings.setValue("last-dir", os.path.dirname(path))
        doc.view.store_view_state()
        try:
            from polytess.graph.lineage import save_with_history
            save_with_history(doc.graph, path)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        doc.path = path
        doc.dirty = False
        self._refresh_tab_title(doc)
        self._push_recent(path)
        self.statusBar().showMessage(
            f"Saved {path}  [{doc.graph.lineage.tag}]", 4000)
        return True

    def _push_recent(self, path: str) -> None:
        recent = [p for p in self._recent_files() if p != path]
        recent.insert(0, path)
        self.settings.setValue("recent-files", ";".join(recent[:MAX_RECENT]))
        self._rebuild_recent_menu()

    def _recent_files(self) -> list[str]:
        raw = str(self.settings.value("recent-files", ""))
        return [p for p in raw.split(";") if p]

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        for path in self._recent_files():
            action = self.recent_menu.addAction(os.path.basename(path))
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, p=path: self.open_document(p))

    def _open_subgraph(self, file: str) -> None:
        doc = self.current_document()
        base = os.path.dirname(doc.path) if doc is not None and doc.path else os.getcwd()
        path = file if os.path.isabs(file) else os.path.join(base, file)
        if not os.path.isfile(path):
            answer = QMessageBox.question(
                self, "Sub-workflow", f"{path}\ndoes not exist. Create it?")
            if answer != QMessageBox.Yes:
                return
            graph = Graph(os.path.basename(path).replace(Graph.FILE_SUFFIX, ""))
            graph.ensure_endpoints()
            graph.save(path)
        self.open_document(path)

    # ---- inspector plumbing --------------------------------------------------------------- #

    def _on_selection(self, node) -> None:
        doc = self.current_document()
        self.inspector.set_node(node, doc.graph if doc is not None else None)

    def _on_node_edited(self, node) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.scene.update_node(node)
            self._mark_dirty(doc)

    def _on_graph_edited(self) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.scene.sync_items()
            self._mark_dirty(doc)

    # ---- variable references --------------------------------------------------------------- #

    def _show_references(self, name: str, scope: str) -> None:
        doc = self.current_document()
        if doc is None:
            return
        from polytess.core.refs import find_references
        from polytess.gui.refs_dialog import ReferencesDialog
        references = find_references(doc.graph, name, scope)

        def goto(guid: str, d=doc):
            item = d.scene.node_items.get(guid)
            if item is not None:
                d.scene.clearSelection()
                item.setSelected(True)
                d.view.centerOn(item)

        dialog = ReferencesDialog(name, scope, references, on_goto=goto, parent=self)
        dialog.show()

    # ---- view helpers ------------------------------------------------------------------------ #

    def _zoom_fit(self) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.view.zoom_fit()

    def _toggle_minimap(self, checked: bool) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.view.minimap.setVisible(checked)

    def _restore_default_layout(self) -> None:
        self.restoreState(self._default_dock_state)

    def _add_node(self) -> None:
        doc = self.current_document()
        if doc is not None:
            center = doc.view.viewport().rect().center()
            doc.view.open_create_menu(doc.view.mapToGlobal(center))

    def _open_manual(self) -> None:
        from polytess.gui.help_browser import HelpWindow
        if getattr(self, "_help_window", None) is None:
            self._help_window = HelpWindow(self)
        self._help_window.show()
        self._help_window.raise_()

    def _new_from_example(self) -> None:
        from polytess.gui.example_gallery import ExampleGalleryDialog
        dialog = ExampleGalleryDialog(self)
        if not dialog.exec() or not dialog.selected_path:
            return
        try:
            graph = Graph.load(dialog.selected_path)
        except Exception as exc:
            QMessageBox.critical(self, "New from Example", str(exc))
            return
        graph.ensure_endpoints()
        graph.path = ""                    # opens as an unsaved copy
        from polytess.graph.lineage import Lineage
        graph.lineage = Lineage()          # fresh identity, own history
        self._add_document(GraphDocument(graph))
        self.statusBar().showMessage(
            f"Example opened as unsaved copy — save it wherever you like.",
            5000)

    def _open_license(self) -> None:
        from polytess.gui.license_dialog import LicenseDialog
        LicenseDialog(self).exec()

    def _show_about(self) -> None:
        from polytess import __version__
        from polytess.core.licensing import license_status
        QMessageBox.about(
            self, "About polytess",
            f"<h3>polytess Studio {__version__}</h3>"
            f"<p>AI-powered visual workflow studio for engineering "
            f"computations.</p>"
            f"<p>{license_status()}</p>"
            f"<p>© 2026 Winthir Studios — "
            f"<a href='https://www.winthirstudios.com/polytess.html'>"
            f"winthirstudios.com</a></p>")

    def _open_settings(self) -> None:
        from polytess.gui.settings_dialog import SettingsDialog
        SettingsDialog(self).exec()

    def _open_code_editor(self) -> None:
        from polytess.gui.code_editor import CodeEditorPanel
        for index in range(self.tabs.count()):
            if isinstance(self.tabs.widget(index), CodeEditorPanel):
                self.tabs.setCurrentIndex(index)
                return
        editor = CodeEditorPanel()
        editor.status_message.connect(
            lambda text: self.statusBar().showMessage(text, 5000))
        index = self.tabs.addTab(editor, icon("edit", "teal"), "Code Editor")
        self.tabs.setCurrentIndex(index)

    def _open_flow_assistant(self) -> None:
        dock = getattr(self, "dock_flow_assistant", None)
        if dock is None:
            from polytess.gui.flow_assistant import FlowAssistantPanel

            def open_graph():
                doc = self.current_document()
                return doc.graph if doc is not None else None

            panel = FlowAssistantPanel(graph_provider=open_graph)
            panel.open_graph.connect(self._open_built_graph)
            panel.status_message.connect(
                lambda text: self.statusBar().showMessage(text, 5000))
            dock = self._add_dock("Flow Assistant", panel,
                                  Qt.RightDockWidgetArea, min_width=380)
            # dock as a tab next to the Inspector (drag it out to
            # rearrange; the X closes it, View menu reopens it)
            inspector_dock = getattr(self, "dock_inspector", None)
            if inspector_dock is not None:
                self.tabifyDockWidget(inspector_dock, dock)
            if getattr(self, "_view_menu", None) is not None:
                self._view_menu.insertAction(self._dock_toggle_separator,
                                             dock.toggleViewAction())
        dock.show()
        dock.raise_()
        dock.widget().input.setFocus()

    def _open_built_graph(self, graph) -> None:
        """A flow built by the flow assistant becomes a new document tab."""
        self._add_document(GraphDocument(graph))

    # ---- flow lifecycle -------------------------------------------------------- #

    def _branch_current(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        if not doc.path:
            QMessageBox.information(self, "Create branch",
                                    "Save the flow first — branches live "
                                    "next to their parent file.")
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Create branch",
            f"Branch of  {doc.graph.lineage.tag}  — name:")
        name = name.strip().replace("@", "-").replace("/", "-")
        if not ok or not name:
            return
        from polytess.graph.lineage import (branch_file_path, branch_graph,
                                            save_with_history)
        branched = branch_graph(doc.graph, name)
        path = branch_file_path(doc.path, name)
        if os.path.isfile(path):
            QMessageBox.warning(self, "Create branch",
                                f"{os.path.basename(path)} already exists.")
            return
        save_with_history(branched, path)
        self.open_document(path)
        self.statusBar().showMessage(
            f"Branch '{name}' created from {doc.graph.lineage.tag}", 5000)

    def _parent_path_for(self, doc) -> str:
        from polytess.graph.lineage import find_parent_path
        path = find_parent_path(doc.path or "")
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select parent flow",
                os.path.dirname(doc.path or ""),
                f"Workflows (*{Graph.FILE_SUFFIX})")
        return path

    def _compare_current(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        parent_path = self._parent_path_for(doc)
        if not parent_path:
            return
        from polytess.graph.lineage import diff_graphs
        try:
            parent = Graph.load(parent_path)
        except Exception as exc:
            QMessageBox.critical(self, "Compare flows", str(exc))
            return
        from polytess.gui.lineage_dialogs import FlowDiffDialog
        diff = diff_graphs(parent, doc.graph)
        # non-modal: clicking a difference jumps to the node on the canvas
        self._diff_dialog = FlowDiffDialog(
            diff, parent.lineage.tag, doc.graph.lineage.tag, self,
            jump_callback=self._jump_to_node)
        self._diff_dialog.show()

    def _jump_to_node(self, guid: str) -> None:
        """Select + center the node and show it in the inspector."""
        doc = self.current_document()
        if doc is None:
            return
        node = doc.graph.node_by_guid(guid)
        if node is None:
            self.statusBar().showMessage(
                "Node is not part of this flow (it only exists on the "
                "other side of the comparison).", 4000)
            return
        doc.scene.clearSelection()
        for item in doc.scene.items():
            if getattr(item, "node", None) is node:
                item.setSelected(True)
                doc.view.centerOn(item)
                break
        self.inspector.set_node(node, doc.graph)

    def _promote_current(self) -> None:
        doc = self.current_document()
        if doc is None or not doc.graph.lineage.has_parent:
            QMessageBox.information(self, "Promote",
                                    "This flow has no parent — create a "
                                    "branch first.")
            return
        parent_path = self._parent_path_for(doc)
        if not parent_path:
            return
        from polytess.graph.lineage import diff_graphs, promote_graph
        try:
            parent = Graph.load(parent_path)
            summary = diff_graphs(parent, doc.graph).summary()
            answer = QMessageBox.question(
                self, "Promote to parent",
                f"Replace  {parent.lineage.tag}  with  "
                f"{doc.graph.lineage.tag}?\n\nChanges: {summary}\n\nThe "
                f"current parent state is kept as a history snapshot.")
            if answer != QMessageBox.Yes:
                return
            promote_graph(doc.graph, parent_path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Promote failed", str(exc))
            return
        # reload the parent tab if it is open (its file changed on disk)
        for index in range(self.tabs.count()):
            open_doc = self.tabs.widget(index)
            if isinstance(open_doc, GraphDocument) \
                    and open_doc.path == os.path.abspath(parent_path):
                open_doc.dirty = False
                self.tabs.removeTab(index)
                break
        self.open_document(parent_path)
        self.statusBar().showMessage(
            f"Promoted {doc.graph.lineage.tag} to "
            f"{os.path.basename(parent_path)}", 5000)

    def _export_documentation(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        default = os.path.splitext(doc.path or doc.graph.name)[0]
        default = default.replace(".flow", "") + "_doc.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export flow documentation", default, "PDF (*.pdf)")
        if not path:
            return
        try:
            from polytess.graph.flow_doc import generate_flow_doc
            generate_flow_doc(doc.graph, path, source_path=doc.path)
        except ImportError:
            QMessageBox.critical(self, "Export documentation",
                                 "The 'reportlab' package is not installed "
                                 "— run: pip install reportlab")
            return
        except OSError as exc:
            QMessageBox.critical(self, "Export documentation", str(exc))
            return
        self.statusBar().showMessage(f"Documentation written: {path}", 6000)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _history_current(self) -> None:
        doc = self.current_document()
        if doc is None or not doc.path:
            QMessageBox.information(self, "Flow history",
                                    "Save the flow first — history "
                                    "snapshots live next to the file.")
            return
        from polytess.graph.lineage import list_history
        snapshots = list_history(doc.path, doc.graph.lineage.flow_id)
        if not snapshots:
            QMessageBox.information(self, "Flow history",
                                    "No snapshots yet — every save files "
                                    "one automatically.")
            return
        from polytess.gui.lineage_dialogs import FlowHistoryDialog
        FlowHistoryDialog(snapshots, self.open_document, self).exec()

    # ---- run control ---------------------------------------------------------------------------- #

    def run_current(self) -> None:
        doc = self.current_document()
        if doc is None or doc.is_running:
            return
        graph = doc.graph
        workdir = os.path.dirname(doc.path) if doc.path else os.getcwd()
        doc.scene.clear_statuses()
        self.log.separator(f"Run: {graph.name} ({doc.title.rstrip(' •')}) "
                           f"[{graph.lineage.tag}]")

        ctx = Context(graph=graph, workdir=workdir, logger=self.log.log)
        processor = GraphProcessor(
            graph, on_status=lambda node, status, d=doc: self._on_status(d, node, status))
        processor.on_state.append(lambda state, d=doc: self._on_run_state(d, state))
        doc.run_ctx = ctx
        doc.processor = processor

        async def runner():
            try:
                await processor.run(ctx)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.log.log("error", f"Run crashed: {exc.__class__.__name__}: {exc}")

        doc.run_task = asyncio.ensure_future(runner())
        doc.run_task.add_done_callback(lambda _t, d=doc: self._on_run_done(d))
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.act_pause.setEnabled(True)
        self.act_pause.setChecked(False)
        self.act_step.setEnabled(True)
        self.statusBar().showMessage("Running…")

    def pause_current(self, checked: bool) -> None:
        doc = self.current_document()
        if doc is None or doc.processor is None:
            return
        if checked:
            doc.processor.pause()
            self.log.log("info", "Paused — nodes finish their current action, "
                                 "no new node starts")
        else:
            doc.processor.resume()
            self.log.log("info", "Resumed")

    def step_current(self) -> None:
        doc = self.current_document()
        if doc is None or doc.processor is None:
            return
        doc.processor.step()

    def _on_run_state(self, doc: GraphDocument, state: str) -> None:
        if doc is not self.current_document():
            return
        paused = state == "paused"
        self.act_pause.setChecked(paused)
        self.statusBar().showMessage("Paused — F7 steps one node, F6 resumes"
                                     if paused else "Running…")

    def stop_current(self) -> None:
        doc = self.current_document()
        if doc is None or not doc.is_running:
            return
        if doc.processor is not None and doc.processor.is_paused:
            doc.processor.resume()      # release gated nodes so they can cancel
        if doc.run_ctx is not None:
            doc.run_ctx.cancel()
        if doc.processor is not None:
            doc.processor.stop()
        self.log.log("warning", "Stop requested")

    def _on_status(self, doc: GraphDocument, node, status: NodeStatus) -> None:
        doc.scene.set_status(node, status.value)

    def _on_run_done(self, doc: GraphDocument) -> None:
        self.log.separator("Run finished")
        doc.run_task = None
        doc.processor = None
        doc.run_ctx = None
        if doc is self.current_document():
            self.act_run.setEnabled(True)
            self.act_stop.setEnabled(False)
            self.act_pause.setEnabled(False)
            self.act_pause.setChecked(False)
            self.act_step.setEnabled(False)
            self.statusBar().showMessage("Ready", 4000)
        self.blackboard.set_graph(doc.graph)

    def validate_current(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        problems = []
        guids = {n.guid for n in doc.graph.nodes}
        for edge in doc.graph.edges:
            if edge.src_node not in guids or edge.dst_node not in guids:
                problems.append(f"Dangling edge {edge!r}")
        from polytess.graph.nodes import StartNode, TriggerNode
        if not any(isinstance(n, (StartNode, TriggerNode)) for n in doc.graph.nodes):
            problems.append("No entry point (Start or Trigger node)")
        if problems:
            for problem in problems:
                self.log.log("error", problem)
            QMessageBox.warning(self, "Validation", "\n".join(problems))
        else:
            self.statusBar().showMessage("Workflow is valid", 4000)

    # ---- shutdown ------------------------------------------------------------------------------------ #

    def closeEvent(self, event):
        for index in range(self.tabs.count()):
            doc = self.tabs.widget(index)
            if isinstance(doc, GraphDocument) and doc.is_running:
                self.stop_current()
        dirty = [self.tabs.widget(i) for i in range(self.tabs.count())
                 if isinstance(self.tabs.widget(i), GraphDocument)
                 and self.tabs.widget(i).dirty]
        if dirty:
            answer = QMessageBox.question(
                self, "Unsaved changes",
                f"{len(dirty)} workflow(s) have unsaved changes. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        super().closeEvent(event)
        QApplication.quit()
