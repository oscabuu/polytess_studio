# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Group frames and sticky notes."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsObject, QInputDialog)

from polytess.gui.theme import ACCENTS, COLORS

GRIP = 14.0


class _ResizableRectItem(QGraphicsObject):
    """Movable + bottom-right resizable rounded rect."""

    MIN_W, MIN_H = 120.0, 80.0

    def __init__(self, scene, model):
        super().__init__()
        self.scene_ref = scene
        self.model = model
        self._resizing = False
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setPos(model.x, model.y)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.model.width, self.model.height)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.model.x = self.pos().x()
            self.model.y = self.pos().y()
            self.scene_ref.mark_modified()
        return super().itemChange(change, value)

    def _grip_rect(self) -> QRectF:
        return QRectF(self.model.width - GRIP, self.model.height - GRIP, GRIP, GRIP)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._grip_rect().contains(event.pos()):
            self._resizing = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.prepareGeometryChange()
            self.model.width = max(self.MIN_W, event.pos().x())
            self.model.height = max(self.MIN_H, event.pos().y())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self.scene_ref.mark_modified()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class GroupItem(_ResizableRectItem):

    TITLE_H = 26.0

    def __init__(self, scene, group):
        super().__init__(scene, group)
        self.setZValue(-10)
        self._grabbed: list = []

    def shape(self):
        """Only the title bar and the resize grip are clickable — clicks and
        rubber-band selection inside the group body reach the nodes."""
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRect(QRectF(0, 0, self.model.width, self.TITLE_H))
        path.addRect(self._grip_rect())
        return path

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._grip_rect().contains(event.pos()):
            # nodes whose center lies inside move with the group
            rect = QRectF(self.pos().x(), self.pos().y(),
                          self.model.width, self.model.height)
            self._grabbed = []
            for item in self.scene_ref.node_items.values():
                center = item.pos() + QPointF(item.width / 2, item.height / 2)
                if rect.contains(center):
                    self._grabbed.append((item, item.pos() - self.pos()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if not self._resizing:
            for item, offset in self._grabbed:
                item.setPos(self.pos() + offset)

    def mouseReleaseEvent(self, event):
        self._grabbed = []
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        title, ok = QInputDialog.getText(None, "Group", "Title:", text=self.model.title)
        if ok:
            self.model.title = title
            self.scene_ref.mark_modified()
            self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        color = QColor(self.model.color)
        fill = QColor(color)
        fill.setAlphaF(0.10)
        painter.setPen(QPen(color if not self.isSelected()
                            else QColor(COLORS["border-active"]), 1.6))
        painter.setBrush(fill)
        painter.drawRoundedRect(self.boundingRect(), 6, 6)
        title_fill = QColor(color)
        title_fill.setAlphaF(0.28)
        painter.setPen(Qt.NoPen)
        painter.setBrush(title_fill)
        painter.drawRoundedRect(QRectF(0, 0, self.model.width, self.TITLE_H), 6, 6)
        painter.drawRect(QRectF(0, self.TITLE_H - 6, self.model.width, 6))
        font = QFont(painter.font())
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color.lighter(150))
        painter.drawText(QRectF(8, 4, self.model.width - 16, 20),
                         Qt.AlignVCenter | Qt.AlignLeft, self.model.title)
        painter.setPen(QPen(color, 1))
        grip = self._grip_rect()
        painter.drawLine(grip.bottomLeft(), grip.topRight())


class StickyNoteItem(_ResizableRectItem):

    def __init__(self, scene, note):
        super().__init__(scene, note)
        self.setZValue(-5)

    def mouseDoubleClickEvent(self, event):
        title, ok = QInputDialog.getText(None, "Sticky Note", "Title:",
                                         text=self.model.title)
        if not ok:
            return
        content, ok = QInputDialog.getMultiLineText(None, "Sticky Note", "Text:",
                                                    self.model.content)
        if ok:
            self.model.title = title
            self.model.content = content
            self.scene_ref.mark_modified()
            self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        bg = QColor("#665c22")
        painter.setPen(QPen(QColor(COLORS["border-active"]) if self.isSelected()
                            else QColor("#8a7d2e"), 1.4))
        painter.setBrush(bg)
        painter.drawRoundedRect(self.boundingRect(), 4, 4)
        font = QFont(painter.font())
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ACCENTS["text"]))
        painter.drawText(QRectF(8, 4, self.model.width - 16, 18),
                         Qt.AlignVCenter | Qt.AlignLeft, self.model.title)
        font.setBold(False)
        font.setPixelSize(10)
        painter.setFont(font)
        painter.drawText(QRectF(8, 24, self.model.width - 16, self.model.height - 30),
                         Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
                         self.model.content)
