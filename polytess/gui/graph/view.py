# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""GraphView — pan/zoom viewport with context menu, keyboard shortcuts
and the minimap overlay."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QGraphicsView, QMenu

from polytess.core.metadata import iter_subclasses
from polytess.graph.model import Node
from polytess.gui.graph.minimap import MiniMap
from polytess.gui.graph.scene import GraphScene
from polytess.gui.type_selector import TypeSelectorPopup

ZOOM_MIN, ZOOM_MAX = 0.2, 2.5


class GraphView(QGraphicsView):

    def __init__(self, scene: GraphScene, parent=None):
        super().__init__(scene, parent)
        self.graph_scene = scene
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._panning = False
        self._pan_start = QPoint()

        self.minimap = MiniMap(self)
        self.minimap.move(8, 8)
        self.minimap.show()

        QShortcut(QKeySequence("F"), self, activated=self.zoom_fit)
        QShortcut(QKeySequence.Delete, self, activated=scene.delete_selection)
        QShortcut(QKeySequence("Backspace"), self, activated=scene.delete_selection)
        QShortcut(QKeySequence.Copy, self, activated=scene.copy_selection)
        QShortcut(QKeySequence.Paste, self, activated=self._paste_at_cursor)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=scene.duplicate_selection)
        QShortcut(QKeySequence("B"), self, activated=scene.toggle_breakpoints)
        QShortcut(QKeySequence("Ctrl+A"), self,
                  activated=lambda: [i.setSelected(True) for i in scene.items()])

        self.restore_view_state()

    # ---- view state persistence ------------ #

    def restore_view_state(self) -> None:
        graph = self.graph_scene.graph
        zoom = min(max(graph.zoom, ZOOM_MIN), ZOOM_MAX)
        self.resetTransform()
        self.scale(zoom, zoom)
        self.centerOn(graph.pan_x, graph.pan_y)

    def store_view_state(self) -> None:
        graph = self.graph_scene.graph
        graph.zoom = self.transform().m11()
        center = self.mapToScene(self.viewport().rect().center())
        graph.pan_x, graph.pan_y = center.x(), center.y()

    # ---- zoom / pan --------------------------------------------------------------- #

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = self.transform().m11()
        target = min(max(current * factor, ZOOM_MIN), ZOOM_MAX)
        factor = target / current
        self.scale(factor, factor)
        self.minimap.schedule_update()

    def zoom_fit(self) -> None:
        rect = self.scene().itemsBoundingRect().adjusted(-60, -60, 60, 60)
        if rect.isValid():
            self.fitInView(rect, Qt.KeepAspectRatio)
            current = self.transform().m11()
            if current > 1.0:
                self.scale(1.0 / current, 1.0 / current)
            self.minimap.schedule_update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            self.minimap.schedule_update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ---- context menu ---------------------------------------------------------------- #

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        scene_pos = self.mapToScene(event.pos())
        menu = QMenu(self)
        menu.addAction("Add Node…", lambda: self.open_create_menu(
            event.globalPos(), scene_pos))
        menu.addSeparator()
        menu.addAction("Add Group", lambda: self.graph_scene.add_group_at(scene_pos))
        menu.addAction("Add Sticky Note", lambda: self.graph_scene.add_note_at(scene_pos))
        menu.addSeparator()
        menu.addAction("Copy", self.graph_scene.copy_selection)
        menu.addAction("Paste", lambda: self.graph_scene.paste(scene_pos))
        menu.addAction("Delete", self.graph_scene.delete_selection)
        if self.graph_scene.selected_nodes():
            menu.addSeparator()
            menu.addAction("Toggle Breakpoint  (B)",
                           self.graph_scene.toggle_breakpoints)
        menu.addSeparator()
        menu.addAction("Zoom to Fit  (F)", self.zoom_fit)
        if item is not None:
            menu.addSeparator()
        menu.exec(event.globalPos())

    def open_create_menu(self, global_pos: QPoint, scene_pos: QPointF | None = None) -> None:
        if scene_pos is None:
            scene_pos = self.mapToScene(self.viewport().rect().center())
        candidates = list(iter_subclasses(Node))

        def pick(cls):
            self.graph_scene.add_node_at(cls, scene_pos)

        popup = TypeSelectorPopup(candidates, pick, parent=self.window(),
                                  favorites_key="nodes")
        popup.open_at(global_pos)

    def _paste_at_cursor(self) -> None:
        view_pos = self.mapFromGlobal(QCursor.pos())
        if self.viewport().rect().contains(view_pos):
            self.graph_scene.paste(self.mapToScene(view_pos))
        else:
            self.graph_scene.paste(None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.minimap.schedule_update()
