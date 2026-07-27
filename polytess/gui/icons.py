# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Programmatic monochrome icons, tintable like IIcon textures.

``icon(name, color)`` returns a cached QIcon backed by a vector icon engine:
every requested size (and device pixel ratio) is painted fresh from the
32-unit design grid — no bitmap rescaling, crisp at any DPI."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QIcon, QIconEngine, QPainter, QPainterPath,
                           QPen, QPixmap, QPolygonF)

from polytess.gui.theme import ACCENTS

_CACHE: dict[tuple[str, str], QIcon] = {}

S = 32.0   # design grid


def _pen(color: QColor, width: float = 3.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _draw(name: str, p: QPainter, c: QColor) -> None:   # noqa: C901
    p.setRenderHint(QPainter.Antialiasing)
    pen = _pen(c)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def fill():
        p.setBrush(c)

    if name == "circle":
        fill(); p.drawEllipse(QRectF(8, 8, 16, 16))
    elif name == "null":
        p.drawEllipse(QRectF(8, 8, 16, 16))
        p.drawLine(QPointF(11, 21), QPointF(21, 11))
    elif name == "play":
        fill(); p.drawPolygon(QPolygonF([QPointF(10, 7), QPointF(25, 16), QPointF(10, 25)]))
    elif name == "stop":
        fill(); p.drawRect(QRectF(9, 9, 14, 14))
    elif name == "pause":
        fill(); p.drawRect(QRectF(9, 8, 4, 16)); p.drawRect(QRectF(19, 8, 4, 16))
    elif name == "step":
        fill()
        p.drawPolygon(QPolygonF([QPointF(7, 7), QPointF(20, 16), QPointF(7, 25)]))
        p.drawRect(QRectF(22, 7, 4, 18))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(5, 10); path.lineTo(12, 10); path.lineTo(14, 13); path.lineTo(27, 13)
        path.lineTo(27, 25); path.lineTo(5, 25); path.closeSubpath()
        fill(); p.drawPath(path)
    elif name == "file":
        path = QPainterPath()
        path.moveTo(9, 5); path.lineTo(19, 5); path.lineTo(24, 10); path.lineTo(24, 27)
        path.lineTo(9, 27); path.closeSubpath()
        p.drawPath(path); p.drawLine(QPointF(19, 5), QPointF(19, 10)); p.drawLine(QPointF(19, 10), QPointF(24, 10))
    elif name == "string":
        f = p.font(); f.setPixelSize(26); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(0, 0, S, S), Qt.AlignCenter, "S")
    elif name == "number":
        f = p.font(); f.setPixelSize(26); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(0, 0, S, S), Qt.AlignCenter, "#")
    elif name == "toggle":
        p.drawRoundedRect(QRectF(5, 11, 22, 10), 5, 5)
        fill(); p.drawEllipse(QRectF(18, 12.5, 7, 7))
    elif name == "list":
        for i, y in enumerate((8, 16, 24)):
            fill(); p.drawEllipse(QRectF(6, y - 1.5, 3, 3))
            p.drawLine(QPointF(13, y), QPointF(26, y))
    elif name == "variable":
        # same visual weight as the 20px "globe" circle (global variables)
        f = p.font(); f.setPixelSize(26); f.setBold(True); f.setItalic(True); p.setFont(f)
        p.drawText(QRectF(0, 0, S, S), Qt.AlignCenter, "x")
    elif name == "globe":
        p.drawEllipse(QRectF(6, 6, 20, 20))
        p.drawEllipse(QRectF(11, 6, 10, 20))
        p.drawLine(QPointF(6, 16), QPointF(26, 16))
    elif name == "clock":
        p.drawEllipse(QRectF(6, 6, 20, 20))
        p.drawLine(QPointF(16, 10), QPointF(16, 16)); p.drawLine(QPointF(16, 16), QPointF(21, 19))
    elif name == "bolt":
        fill()
        p.drawPolygon(QPolygonF([QPointF(18, 4), QPointF(8, 18), QPointF(14, 18),
                                 QPointF(12, 28), QPointF(24, 13), QPointF(17, 13)]))
    elif name == "branch":
        p.drawLine(QPointF(9, 26), QPointF(9, 12))
        p.drawEllipse(QRectF(6, 24, 6, 6)); p.drawEllipse(QRectF(6, 5, 6, 6))
        p.drawEllipse(QRectF(21, 5, 6, 6))
        path = QPainterPath(); path.moveTo(9, 18); path.cubicTo(9, 12, 24, 16, 24, 11)
        p.drawPath(path)
    elif name == "diamond":
        fill(); p.drawPolygon(QPolygonF([QPointF(16, 5), QPointF(27, 16), QPointF(16, 27), QPointF(5, 16)]))
    elif name == "check":
        p.setPen(_pen(c, 4)); p.drawPolyline(QPolygonF([QPointF(7, 17), QPointF(13, 23), QPointF(25, 9)]))
    elif name == "cancel":
        p.setPen(_pen(c, 4)); p.drawLine(QPointF(9, 9), QPointF(23, 23)); p.drawLine(QPointF(23, 9), QPointF(9, 23))
    elif name == "trash":
        p.drawRect(QRectF(9, 11, 14, 15)); p.drawLine(QPointF(6, 11), QPointF(26, 11))
        p.drawLine(QPointF(13, 7), QPointF(19, 7))
        p.drawLine(QPointF(13, 15), QPointF(13, 22)); p.drawLine(QPointF(19, 15), QPointF(19, 22))
    elif name == "duplicate":
        p.drawRect(QRectF(7, 7, 13, 13)); p.drawRect(QRectF(12, 12, 13, 13))
    elif name == "edit":
        p.drawLine(QPointF(7, 25), QPointF(11, 25))
        p.drawPolygon(QPolygonF([QPointF(8, 20), QPointF(21, 7), QPointF(25, 11), QPointF(12, 24)]))
    elif name == "search":
        p.drawEllipse(QRectF(6, 6, 14, 14)); p.setPen(_pen(c, 4)); p.drawLine(QPointF(19, 19), QPointF(26, 26))
    elif name == "terminal":
        p.drawRoundedRect(QRectF(4, 6, 24, 20), 2, 2)
        p.drawPolyline(QPolygonF([QPointF(8, 12), QPointF(12, 16), QPointF(8, 20)]))
        p.drawLine(QPointF(15, 21), QPointF(23, 21))
    elif name == "message":
        p.drawRoundedRect(QRectF(5, 6, 22, 16), 3, 3)
        p.drawPolyline(QPolygonF([QPointF(11, 22), QPointF(11, 27), QPointF(17, 22)]))
    elif name == "repeat":
        p.drawArc(QRectF(7, 7, 18, 18), 30 * 16, 300 * 16)
        fill(); p.drawPolygon(QPolygonF([QPointF(26, 4), QPointF(28, 12), QPointF(20, 10)]))
    elif name == "arrow-right":
        p.setPen(_pen(c, 4)); p.drawLine(QPointF(5, 16), QPointF(24, 16))
        p.drawPolyline(QPolygonF([QPointF(18, 9), QPointF(26, 16), QPointF(18, 23)]))
    elif name == "target":
        p.drawEllipse(QRectF(6, 6, 20, 20)); fill(); p.drawEllipse(QRectF(13, 13, 6, 6))
    elif name == "node":
        p.drawRoundedRect(QRectF(6, 9, 20, 14), 3, 3); p.drawLine(QPointF(6, 14), QPointF(26, 14))
    elif name == "graph":
        fill()
        p.drawEllipse(QRectF(4, 4, 8, 8)); p.drawEllipse(QRectF(20, 12, 8, 8)); p.drawEllipse(QRectF(4, 20, 8, 8))
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(11, 8), QPointF(22, 15)); p.drawLine(QPointF(11, 24), QPointF(22, 17))
    elif name == "instructions":
        for y in (8, 14, 20, 26):
            p.drawLine(QPointF(7, y), QPointF(25, y))
    elif name == "conditions":
        p.drawPolygon(QPolygonF([QPointF(16, 5), QPointF(27, 16), QPointF(16, 27), QPointF(5, 16)]))
        p.drawLine(QPointF(12, 16), QPointF(15, 19)); p.drawLine(QPointF(15, 19), QPointF(21, 12))
    elif name == "drag":
        for x in (12, 20):
            for y in (9, 16, 23):
                fill(); p.drawEllipse(QRectF(x - 1.8, y - 1.8, 3.6, 3.6))
    elif name in ("chevron-down", "chevron-right", "chevron-left", "chevron-up"):
        p.setPen(_pen(c, 4))
        if name == "chevron-down":
            pts = [QPointF(8, 12), QPointF(16, 21), QPointF(24, 12)]
        elif name == "chevron-up":
            pts = [QPointF(8, 20), QPointF(16, 11), QPointF(24, 20)]
        elif name == "chevron-right":
            pts = [QPointF(12, 8), QPointF(21, 16), QPointF(12, 24)]
        else:
            pts = [QPointF(20, 8), QPointF(11, 16), QPointF(20, 24)]
        p.drawPolyline(QPolygonF(pts))
    elif name == "plus":
        p.setPen(_pen(c, 4)); p.drawLine(QPointF(16, 7), QPointF(16, 25)); p.drawLine(QPointF(7, 16), QPointF(25, 16))
    elif name == "minus":
        p.setPen(_pen(c, 4)); p.drawLine(QPointF(7, 16), QPointF(25, 16))
    elif name == "breakpoint":
        fill(); p.drawEllipse(QRectF(9, 9, 14, 14))
    elif name == "dropdown":
        fill(); p.drawPolygon(QPolygonF([QPointF(9, 13), QPointF(23, 13), QPointF(16, 22)]))
    elif name == "help":
        f = p.font(); f.setPixelSize(26); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(0, 0, S, S), Qt.AlignCenter, "?")
    elif name == "gear":
        from math import cos, pi, sin
        p.setPen(_pen(c, 3.4))
        p.drawEllipse(QRectF(9, 9, 14, 14))
        for i in range(8):
            a = i * pi / 4
            p.drawLine(QPointF(16 + 8.5 * cos(a), 16 + 8.5 * sin(a)),
                       QPointF(16 + 12 * cos(a), 16 + 12 * sin(a)))
        fill(); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(13.5, 13.5, 5, 5))
    elif name == "axes":
        # vector3: three axes from a shared origin, with arrowheads
        origin = QPointF(9, 24)
        p.drawLine(origin, QPointF(9, 7))
        p.drawLine(origin, QPointF(26, 24))
        p.drawLine(origin, QPointF(21, 12))
        fill()
        p.drawPolygon(QPolygonF([QPointF(6, 9), QPointF(12, 9), QPointF(9, 4)]))
        p.drawPolygon(QPolygonF([QPointF(24, 21), QPointF(24, 27), QPointF(29, 24)]))
        p.drawPolygon(QPolygonF([QPointF(19, 9.5), QPointF(24.5, 15), QPointF(24, 9)]))
    elif name == "transform":
        # pos + rot: a 3D box with a rotation arc
        p.drawRect(QRectF(6, 12, 14, 14))
        p.drawLine(QPointF(6, 12), QPointF(12, 6))
        p.drawLine(QPointF(20, 12), QPointF(26, 6))
        p.drawLine(QPointF(12, 6), QPointF(26, 6))
        p.drawLine(QPointF(26, 6), QPointF(26, 18))
        p.drawLine(QPointF(20, 26), QPointF(26, 18))
        p.drawArc(QRectF(14, 14, 16, 16), 300 * 16, 110 * 16)
    elif name == "note":
        path = QPainterPath()
        path.moveTo(6, 5); path.lineTo(26, 5); path.lineTo(26, 19); path.lineTo(19, 26)
        path.lineTo(6, 26); path.closeSubpath()
        p.drawPath(path); p.drawLine(QPointF(19, 26), QPointF(19, 19)); p.drawLine(QPointF(19, 19), QPointF(26, 19))
    elif name == "group":
        p.setPen(_pen(c, 2.4))
        pen = p.pen(); pen.setStyle(Qt.DashLine); p.setPen(pen)
        p.drawRoundedRect(QRectF(5, 7, 22, 18), 3, 3)
    elif name == "zoom-fit":
        p.drawRect(QRectF(9, 9, 14, 14))
        for x, y, dx, dy in ((5, 5, 4, 4), (27, 5, -4, 4), (5, 27, 4, -4), (27, 27, -4, -4)):
            p.drawLine(QPointF(x, y), QPointF(x + dx, y + dy))
    elif name == "minimap":
        p.drawRect(QRectF(5, 7, 22, 18)); fill(); p.drawRect(QRectF(17, 9, 8, 6))
    elif name == "save":
        path = QPainterPath()
        path.moveTo(6, 6); path.lineTo(22, 6); path.lineTo(26, 10); path.lineTo(26, 26)
        path.lineTo(6, 26); path.closeSubpath()
        p.drawPath(path); p.drawRect(QRectF(11, 17, 10, 9)); p.drawRect(QRectF(11, 6, 8, 6))
    elif name == "filter":
        fill()
        p.drawPolygon(QPolygonF([QPointF(5, 6), QPointF(27, 6), QPointF(19, 16),
                                 QPointF(19, 25), QPointF(13, 28), QPointF(13, 16)]))
    elif name == "star":
        pts = []
        from math import cos, pi, sin
        for i in range(10):
            r = 12 if i % 2 == 0 else 5.5
            a = -pi / 2 + i * pi / 5
            pts.append(QPointF(16 + r * cos(a), 16 + r * sin(a)))
        fill(); p.drawPolygon(QPolygonF(pts))
    elif name in ("undo", "redo"):
        # curved arrow: head top-left (undo) / top-right (redo), swoosh down
        flat = _pen(c)
        flat.setCapStyle(Qt.FlatCap)
        p.setPen(flat)
        if name == "redo":
            p.translate(S, 0)
            p.scale(-1, 1)
        path = QPainterPath()
        path.moveTo(10, 10)
        path.cubicTo(20, 7.5, 25.5, 14, 25, 23)
        p.drawPath(path)
        fill()
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(3.5, 10), QPointF(12, 5), QPointF(12, 15)]))
    else:   # fallback: small circle
        fill(); p.drawEllipse(QRectF(10, 10, 12, 12))


class _VectorIconEngine(QIconEngine):
    """Paints the named shape at whatever size/DPR is requested."""

    def __init__(self, name: str, color: QColor):
        super().__init__()
        self._name = name
        self._color = color

    def clone(self) -> "QIconEngine":
        return _VectorIconEngine(self._name, self._color)

    def paint(self, painter, rect, mode, state) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.topLeft())
        painter.scale(rect.width() / S, rect.height() / S)
        color = QColor(self._color)
        if mode == QIcon.Disabled:
            color.setAlphaF(color.alphaF() * 0.4)
        _draw(self._name, painter, color)
        painter.restore()

    def _render(self, size: QSize, mode, state, scale: float = 1.0) -> QPixmap:
        device = QSize(max(1, round(size.width() * scale)),
                       max(1, round(size.height() * scale)))
        pixmap = QPixmap(device)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(QPoint(0, 0), device), mode, state)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def pixmap(self, size: QSize, mode, state) -> QPixmap:
        return self._render(size, mode, state)

    def scaledPixmap(self, size: QSize, mode, state, scale: float) -> QPixmap:
        return self._render(size, mode, state, scale)


def icon(name: str, color: str = "text", size: int = 32) -> QIcon:
    """Cached vector icon; *size* is kept for API compatibility (the engine
    renders at whatever size is actually requested)."""
    key = (name, color)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    qcol = QColor(ACCENTS.get(color, color))
    result = QIcon(_VectorIconEngine(name, qcol))
    _CACHE[key] = result
    return result


def item_icon(item) -> QIcon:
    """Icon for a PolymorphicItem using its meta icon/color."""
    return icon(item.icon, item.color)
