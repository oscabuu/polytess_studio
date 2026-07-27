# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""EdgeItem — bezier connection + the rubber edge shown
while dragging a new connection."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from polytess.gui.theme import COLORS


def bezier_path(src: QPointF, dst: QPointF, src_vertical: bool,
                dst_vertical: bool) -> QPainterPath:
    path = QPainterPath(src)
    span = max(40.0, min(160.0, abs((dst - src).x()) * 0.5 + abs((dst - src).y()) * 0.25))
    c1 = QPointF(src.x(), src.y() + span) if src_vertical else QPointF(src.x() + span, src.y())
    c2 = QPointF(dst.x(), dst.y() - span) if dst_vertical else QPointF(dst.x() - span, dst.y())
    path.cubicTo(c1, c2, dst)
    return path


class EdgeItem(QGraphicsPathItem):

    def __init__(self, scene, edge):
        super().__init__()
        self.scene_ref = scene
        self.edge = edge
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._hover = False
        self.update_path()

    def update_path(self) -> None:
        src_item = self.scene_ref.node_items.get(self.edge.src_node)
        dst_item = self.scene_ref.node_items.get(self.edge.dst_node)
        if src_item is None or dst_item is None:
            return
        src_spec = src_item.node.port(self.edge.src_port)
        dst_spec = dst_item.node.port(self.edge.dst_port)
        src = src_item.port_scene_pos(self.edge.src_port)
        dst = dst_item.port_scene_pos(self.edge.dst_port)
        self.setPath(bezier_path(src, dst,
                                 bool(src_spec and src_spec.vertical),
                                 bool(dst_spec and dst_spec.vertical)))

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()

    def shape(self):
        # wider hit area
        from PySide6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        if self.isSelected():
            color = QColor(COLORS["border-active"])
            width = 2.6
        elif self._hover:
            color = QColor("#bbbbbb")
            width = 2.4
        else:
            color = QColor("#888888")
            width = 2.0
        painter.setPen(QPen(color, width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())


class PendingEdgeItem(QGraphicsPathItem):
    """Rubber edge while dragging from a port."""

    def __init__(self):
        super().__init__()
        self.setZValue(50)
        pen = QPen(QColor(COLORS["border-active"]), 2, Qt.DashLine)
        self.setPen(pen)

    def update_points(self, src: QPointF, dst: QPointF, src_vertical: bool) -> None:
        self.setPath(bezier_path(src, dst, src_vertical, src_vertical))
