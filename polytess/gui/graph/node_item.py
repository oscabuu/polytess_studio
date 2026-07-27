# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""NodeItem — the visual node: accent title bar with icon,
name, counter badge and expand chevron; expandable body previewing the
payload (action/condition titles); ports left/right (horizontal) and
top/bottom (vertical); live status highlight while running."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from polytess.graph.model import Node, PortSpec
from polytess.gui.theme import (ACCENTS, COLORS, STATUS_COLORS, node_accent)

TITLE_H = 26.0
LINE_H = 17.0
PORT_R = 5.0
PORT_ROW_H = 16.0
MAX_PREVIEW = 8
MIN_WIDTH = 190.0


class NodeItem(QGraphicsObject):

    def __init__(self, scene, node: Node):
        super().__init__()
        self.scene_ref = scene
        self.node = node
        self.status: str = "idle"
        self._drag_start: tuple[float, float] | None = None

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setPos(node.x, node.y)
        self.setZValue(10)
        self._layout()

    # ---- geometry ----------------------------------------------------------- #

    def _layout(self) -> None:
        self.prepareGeometryChange()
        self.width = max(MIN_WIDTH, self.node.width)
        h_out = [p for p in self.node.ports("out") if not p.vertical]
        self.port_rows = h_out if len(h_out) > 1 else []
        self.preview = self.node.content_lines() if self.node.expanded else []
        if len(self.preview) > MAX_PREVIEW:
            self.preview = self.preview[:MAX_PREVIEW]
            self._truncated = True
        else:
            self._truncated = False
        height = TITLE_H
        height += PORT_ROW_H * len(self.port_rows)
        if self.node.expanded:
            count = len(self.preview) + (1 if self._truncated else 0)
            height += 6 + max(1, count) * LINE_H + 6 if count or True else 0
        self.height = height

    def boundingRect(self) -> QRectF:
        return QRectF(-PORT_R - 2, -PORT_R - 2,
                      self.width + 2 * PORT_R + 4, self.height + 2 * PORT_R + 4)

    # ---- ports ------------------------------------------------------------------ #

    def port_pos(self, port: PortSpec) -> QPointF:
        """Port center in item coordinates."""
        if port.vertical:
            x = self.width / 2
            return QPointF(x, 0 if port.direction == "in" else self.height)
        if port.direction == "in":
            return QPointF(0, TITLE_H / 2)
        if self.port_rows and port in self.port_rows:
            index = self.port_rows.index(port)
            return QPointF(self.width, TITLE_H + PORT_ROW_H * (index + 0.5))
        return QPointF(self.width, TITLE_H / 2)

    def port_scene_pos(self, port_name: str) -> QPointF:
        spec = self.node.port(port_name)
        if spec is None:
            return self.mapToScene(QPointF(self.width / 2, self.height / 2))
        return self.mapToScene(self.port_pos(spec))

    def port_at(self, item_pos: QPointF) -> PortSpec | None:
        for spec in self.node.ports():
            center = self.port_pos(spec)
            if (center - item_pos).manhattanLength() <= PORT_R * 2.4:
                return spec
        return None

    # ---- model sync ----------------------------------------------------------------- #

    def sync_from_model(self) -> None:
        self._layout()
        if (self.pos().x(), self.pos().y()) != (self.node.x, self.node.y):
            self.setPos(self.node.x, self.node.y)
        self.update()

    def set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            self.update()

    # ---- interaction -------------------------------------------------------------------- #

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.node.x = self.pos().x()
            self.node.y = self.pos().y()
            self.scene_ref.update_edges_for(self.node.guid)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            chevron = QRectF(self.width - 22, 4, 18, 18)
            if chevron.contains(event.pos()):
                self.node.expanded = not self.node.expanded
                self.sync_from_model()
                self.scene_ref.mark_modified()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        from polytess.graph.nodes import SubGraphNode
        if isinstance(self.node, SubGraphNode) and self.node.file:
            self.scene_ref.request_open_subgraph.emit(self.node.file)
            event.accept()
            return
        self.node.expanded = not self.node.expanded
        self.sync_from_model()
        event.accept()

    # ---- painting ------------------------------------------------------------------------ #

    def paint(self, painter, option, widget=None):   # noqa: C901
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        radius = 6.0
        body_rect = QRectF(0, 0, self.width, self.height)

        # body
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["bg-dark"]))
        painter.drawRoundedRect(body_rect, radius, radius)

        # title bar with accent
        accent = node_accent(self.node.accent)
        title_path = QPainterPath()
        title_path.addRoundedRect(QRectF(0, 0, self.width, TITLE_H), radius, radius)
        title_path.addRect(QRectF(0, TITLE_H - radius, self.width, radius))
        painter.setBrush(QBrush(accent))
        painter.drawPath(title_path.simplified())

        # border by status/selection
        if self.status in STATUS_COLORS:
            pen = QPen(QColor(STATUS_COLORS[self.status]), 2.4)
        elif self.isSelected():
            pen = QPen(QColor(COLORS["border-active"]), 2.0)
        else:
            pen = QPen(QColor(COLORS["border-default"]), 1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(body_rect, radius, radius)

        # title icon (the node's real icon, accent-tinted) + text
        text_color = QColor(ACCENTS["text"]) if self.node.enabled \
            else QColor(ACCENTS["text-light"])
        painter.setPen(Qt.NoPen)
        if self.node.breakpoint:
            # breakpoint: red dot with white ring (debugger convention)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(QRectF(5, TITLE_H / 2 - 7, 14, 14))
            painter.setBrush(QColor("#e04b3a"))
            painter.drawEllipse(QRectF(7, TITLE_H / 2 - 5, 10, 10))
        else:
            from polytess.gui.icons import icon as _icon
            tint = self.node.accent if self.node.accent in ACCENTS else "text"
            pixmap = _icon(self.node.icon, tint).pixmap(14, 14)
            painter.drawPixmap(QPointF(5, TITLE_H / 2 - 7), pixmap)

        font = QFont(painter.font())
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        metrics = QFontMetricsF(font)
        name = metrics.elidedText(self.node.name, Qt.ElideRight, self.width - 78)
        painter.drawText(QRectF(22, 0, self.width - 78, TITLE_H),
                         Qt.AlignVCenter | Qt.AlignLeft, name)

        # counter badge
        count = self.node.counter
        if count:
            badge = QRectF(self.width - 46, TITLE_H / 2 - 8, 20, 16)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 90))
            painter.drawRoundedRect(badge, 8, 8)
            font.setBold(False)
            font.setPixelSize(10)
            painter.setFont(font)
            painter.setPen(text_color)
            painter.drawText(badge, Qt.AlignCenter, str(count))

        # expand chevron
        painter.setPen(QPen(text_color, 2))
        cx, cy = self.width - 14, TITLE_H / 2
        if self.node.expanded:
            painter.drawPolyline([QPointF(cx - 4, cy - 2), QPointF(cx, cy + 3),
                                  QPointF(cx + 4, cy - 2)])
        else:
            painter.drawPolyline([QPointF(cx - 2, cy - 4), QPointF(cx + 3, cy),
                                  QPointF(cx - 2, cy + 4)])

        # multi-out port labels (Conditions: Success / Fail)
        font.setPixelSize(10)
        font.setBold(False)
        painter.setFont(font)
        for index, spec in enumerate(self.port_rows):
            y = TITLE_H + PORT_ROW_H * index
            painter.setPen(QColor(ACCENTS["text-light"]))
            painter.drawText(QRectF(0, y, self.width - 12, PORT_ROW_H),
                             Qt.AlignVCenter | Qt.AlignRight, spec.label)

        # preview body lines
        if self.node.expanded:
            y = TITLE_H + PORT_ROW_H * len(self.port_rows) + 6
            font.setPixelSize(10)
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            if not self.preview:
                painter.setPen(QColor(ACCENTS["text-light"]))
                painter.drawText(QRectF(10, y, self.width - 20, LINE_H),
                                 Qt.AlignVCenter | Qt.AlignLeft, "(empty)")
            for item in self.preview:
                # neutral title text; the colored item icon carries the theme
                from polytess.gui.icons import icon as _icon
                color = QColor(ACCENTS["text"])
                if not item.is_enabled:
                    color = QColor(ACCENTS["text-light"])
                    color.setAlphaF(0.5)
                    painter.setOpacity(0.5)
                pixmap = _icon(item.icon, item.color).pixmap(12, 12)
                painter.drawPixmap(QPointF(8, y + LINE_H / 2 - 6), pixmap)
                painter.setPen(color)
                text = metrics.elidedText(item.title, Qt.ElideRight, self.width - 38)
                painter.drawText(QRectF(24, y, self.width - 34, LINE_H),
                                 Qt.AlignVCenter | Qt.AlignLeft, text)
                painter.setOpacity(1.0)
                y += LINE_H
            if self._truncated:
                painter.setPen(QColor(ACCENTS["text-light"]))
                painter.drawText(QRectF(20, y, self.width - 30, LINE_H),
                                 Qt.AlignVCenter | Qt.AlignLeft, "…")

        # ports
        for spec in self.node.ports():
            center = self.port_pos(spec)
            painter.setPen(QPen(QColor(COLORS["border-default"]), 1))
            if spec.direction == "out":
                painter.setBrush(QColor(ACCENTS.get(self.node.accent, "#87d8f6")))
            else:
                painter.setBrush(QColor(COLORS["bg-lightest"]))
            painter.drawEllipse(center, PORT_R, PORT_R)

        # disabled overlay
        if not self.node.enabled:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 110))
            painter.drawRoundedRect(body_rect, radius, radius)
