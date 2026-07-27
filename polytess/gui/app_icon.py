# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Application icon — a node graph on a dark rounded tile, drawn with
QPainter in the studio's accent colors. Rendered at runtime in all
sizes (no asset files); ``export_png``/``export_iconset`` create files
for packaging (PyInstaller, .icns)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF)

S = 1024.0   # design grid

_BG_TOP = "#3d3d3d"
_BG_BOTTOM = "#232323"
_BORDER = "#151515"
_EDGE = "#c9c9c9"
_PURPLE = "#a692e9"
_BLUE = "#87d8f6"
_GREEN = "#c2f771"
_YELLOW = "#f1c437"


def _node(painter: QPainter, x: float, y: float, w: float, h: float,
          accent: str) -> None:
    """A miniature workflow node: dark body, colored title bar, port dots."""
    radius = 34.0
    body = QRectF(x, y, w, h)
    # drop shadow
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 90))
    painter.drawRoundedRect(body.translated(0, 14), radius, radius)
    # body
    painter.setBrush(QColor("#2e2e2e"))
    painter.setPen(QPen(QColor(_BORDER), 8))
    painter.drawRoundedRect(body, radius, radius)
    # title bar (clipped to the top rounded corners)
    title_height = h * 0.42
    path = QPainterPath()
    path.addRoundedRect(body, radius, radius)
    painter.save()
    painter.setClipPath(path)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(accent))
    painter.drawRect(QRectF(x, y, w, title_height))
    # title dot
    painter.setBrush(QColor("#2e2e2e"))
    painter.drawEllipse(QPointF(x + title_height * 0.55, y + title_height * 0.5),
                        title_height * 0.16, title_height * 0.16)
    # content line hints
    painter.setBrush(QColor(255, 255, 255, 70))
    line_y = y + title_height + (h - title_height) * 0.28
    painter.drawRoundedRect(QRectF(x + w * 0.14, line_y, w * 0.55, 16), 8, 8)
    painter.drawRoundedRect(QRectF(x + w * 0.14, line_y + 44, w * 0.40, 16), 8, 8)
    painter.restore()


def _edge(painter: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    distance = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    span = min(260.0, max(120.0, distance * 0.5))
    path = QPainterPath(QPointF(x1, y1))
    path.cubicTo(QPointF(x1 + span, y1), QPointF(x2 - span, y2), QPointF(x2, y2))
    pen = QPen(QColor(_EDGE), 22)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)


def _port(painter: QPainter, x: float, y: float, color: str) -> None:
    painter.setPen(QPen(QColor(_BORDER), 8))
    painter.setBrush(QColor(color))
    painter.drawEllipse(QPointF(x, y), 26, 26)


def paint_app_icon(painter: QPainter) -> None:
    """Draws the icon into the S×S design grid."""
    painter.setRenderHint(QPainter.Antialiasing)

    # rounded dark tile
    tile = QRectF(40, 40, S - 80, S - 80)
    gradient = QLinearGradient(0, 0, 0, S)
    gradient.setColorAt(0.0, QColor(_BG_TOP))
    gradient.setColorAt(1.0, QColor(_BG_BOTTOM))
    painter.setPen(QPen(QColor(_BORDER), 14))
    painter.setBrush(gradient)
    painter.drawRoundedRect(tile, 190, 190)

    # faint canvas grid
    painter.setPen(QPen(QColor(255, 255, 255, 14), 4))
    for i in range(1, 6):
        offset = 40 + i * (S - 80) / 6
        painter.drawLine(QPointF(offset, 80), QPointF(offset, S - 80))
        painter.drawLine(QPointF(80, offset), QPointF(S - 80, offset))

    # node layout:  purple (start) -> blue (action) -> green (condition)
    p1 = (100.0, 150.0, 290.0, 200.0)    # purple, upper left
    p2 = (250.0, 560.0, 300.0, 210.0)    # blue, lower center-left
    p3 = (640.0, 300.0, 270.0, 180.0)    # green, middle right

    out1 = (p1[0] + p1[2], p1[1] + p1[3] * 0.21)
    in2 = (p2[0], p2[1] + p2[3] * 0.21)
    out2 = (p2[0] + p2[2], p2[1] + p2[3] * 0.21)
    in3 = (p3[0], p3[1] + p3[3] * 0.21)

    # edges beneath the nodes
    _edge(painter, *out1, *in2)
    _edge(painter, *out2, *in3)

    for (x, y, w, h), accent in ((p1, _PURPLE), (p2, _BLUE), (p3, _GREEN)):
        _node(painter, x, y, w, h, accent)

    # ports on the edge endpoints
    _port(painter, *out1, _PURPLE)
    _port(painter, *in2, _BLUE)
    _port(painter, *out2, _BLUE)
    _port(painter, *in3, _GREEN)

    # play badge (bottom right) — the "run" identity of the studio
    badge_center = QPointF(790, 780)
    badge_radius = 128.0
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 110))
    painter.drawEllipse(badge_center + QPointF(0, 10), badge_radius, badge_radius)
    painter.setPen(QPen(QColor(_BORDER), 10))
    painter.setBrush(QColor(_YELLOW))
    painter.drawEllipse(badge_center, badge_radius, badge_radius)
    triangle = QPolygonF([badge_center + QPointF(-42, -62),
                          badge_center + QPointF(74, 0),
                          badge_center + QPointF(-42, 62)])
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#232323"))
    painter.drawPolygon(triangle)


def render_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.scale(size / S, size / S)
    paint_app_icon(painter)
    painter.end()
    return pixmap


_ICON: QIcon | None = None


def app_icon() -> QIcon:
    global _ICON
    if _ICON is None:
        _ICON = QIcon()
        for size in (16, 32, 64, 128, 256, 512, 1024):
            _ICON.addPixmap(render_pixmap(size))
    return _ICON


def export_png(path: str, size: int = 512) -> None:
    render_pixmap(size).save(path, "PNG")


def export_iconset(folder: str) -> None:
    """Writes an .iconset folder (macOS: iconutil -c icns <folder>)."""
    import os
    os.makedirs(folder, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        render_pixmap(size).save(os.path.join(folder, f"icon_{size}x{size}.png"), "PNG")
        render_pixmap(size * 2).save(
            os.path.join(folder, f"icon_{size}x{size}@2x.png"), "PNG")
