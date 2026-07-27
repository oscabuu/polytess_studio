# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Minimap overlay: thumbnail of the whole graph with the
current viewport rectangle; click/drag to navigate."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from polytess.gui.theme import COLORS

W, H = 200, 110


class MiniMap(QWidget):

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setFixedSize(W, H)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.update)
        self._refresh = QTimer(self)
        self._refresh.setInterval(600)
        self._refresh.timeout.connect(self.update)
        self._refresh.start()

    def schedule_update(self) -> None:
        if self.isVisible():
            self._timer.start()

    def _scene_rect(self) -> QRectF:
        rect = self.view.scene().itemsBoundingRect().adjusted(-80, -80, 80, 80)
        if not rect.isValid() or rect.width() < 1:
            rect = QRectF(-400, -300, 800, 600)
        return rect

    def _map_factor(self, rect: QRectF) -> float:
        return min((W - 8) / rect.width(), (H - 8) / rect.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["border-hover"]), 1))
        bg = QColor(COLORS["bg-darkest"])
        bg.setAlphaF(0.9)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 3, 3)

        rect = self._scene_rect()
        factor = self._map_factor(rect)

        def to_map(scene_pt):
            return ((scene_pt.x() - rect.x()) * factor + 4,
                    (scene_pt.y() - rect.y()) * factor + 4)

        # nodes
        scene = self.view.graph_scene
        for item in scene.node_items.values():
            x, y = to_map(item.pos())
            w = max(3.0, item.width * factor)
            h = max(2.0, item.height * factor)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(COLORS["bg-lightest"]))
            painter.drawRect(QRectF(x, y, w, h))

        # viewport
        viewport_rect = self.view.mapToScene(
            self.view.viewport().rect()).boundingRect()
        x, y = to_map(viewport_rect.topLeft())
        painter.setPen(QPen(QColor(COLORS["border-active"]), 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(x, y, viewport_rect.width() * factor,
                                viewport_rect.height() * factor))

    def _navigate(self, pos) -> None:
        rect = self._scene_rect()
        factor = self._map_factor(rect)
        scene_x = (pos.x() - 4) / factor + rect.x()
        scene_y = (pos.y() - 4) / factor + rect.y()
        self.view.centerOn(scene_x, scene_y)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._navigate(event.position())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._navigate(event.position())
            event.accept()
