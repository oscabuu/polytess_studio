# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Application icons — the "P" monogram on a dark rounded tile, drawn
with QPainter in the accent colors (design chosen 2026-10-25):

- **studio**: the P is one thick light-blue connector stroke; its bowl
  ends in a purple port, its stem in a green port.
- **viewer**: the same P in lime green with a single green port at the
  stem's foot and a white play triangle inside the bowl.

Rendered at runtime in all sizes (no asset files); ``export_png`` /
``export_iconset`` create files for packaging (PyInstaller, .icns)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF)

S = 1024.0   # design grid

_BG_TOP = "#2b2b2b"
_BG_BOTTOM = "#1f1f1f"
_BORDER = "#151515"
_PURPLE = "#a692e9"
_BLUE = "#87d8f6"
_GREEN = "#c2f771"
_WHITE = "#f4f4f4"

VARIANTS = ("studio", "viewer")

# geometry of the P (design grid): stem x, top y, bottom y, bowl extents
_STEM_X = 345.0
_TOP_Y = 265.0
_BOTTOM_Y = 760.0
_BOWL_RIGHT = 715.0
_BOWL_BOTTOM = 528.0
_STROKE = 68.0
_PORT_R = 58.0


def _tile(painter: QPainter) -> None:
    tile = QRectF(60, 60, S - 120, S - 120)
    gradient = QLinearGradient(0, 0, 0, S)
    gradient.setColorAt(0.0, QColor(_BG_TOP))
    gradient.setColorAt(1.0, QColor(_BG_BOTTOM))
    painter.setPen(QPen(QColor(_BORDER), 10))
    painter.setBrush(gradient)
    painter.drawRoundedRect(tile, 190, 190)


def _p_path() -> QPainterPath:
    """The P as a single open stroke: stem bottom → top → bowl → back
    into the stem (the bowl closes onto the stem a little above the
    stem's middle, like a connector returning to its node)."""
    path = QPainterPath(QPointF(_STEM_X, _BOTTOM_Y))
    path.lineTo(QPointF(_STEM_X, _TOP_Y + 90))
    path.quadTo(QPointF(_STEM_X, _TOP_Y), QPointF(_STEM_X + 90, _TOP_Y))
    path.lineTo(QPointF(_BOWL_RIGHT - 140, _TOP_Y))
    # right side of the bowl: a generous rounded corner down to the bowl bottom
    path.cubicTo(QPointF(_BOWL_RIGHT + 60, _TOP_Y),
                 QPointF(_BOWL_RIGHT + 60, _BOWL_BOTTOM),
                 QPointF(_BOWL_RIGHT - 140, _BOWL_BOTTOM))
    path.lineTo(QPointF(_STEM_X + 120, _BOWL_BOTTOM))
    path.quadTo(QPointF(_STEM_X + 10, _BOWL_BOTTOM), QPointF(_STEM_X, _BOWL_BOTTOM + 70))
    return path


def _stroke(painter: QPainter, path: QPainterPath, color: str) -> None:
    pen = QPen(QColor(color), _STROKE)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)


def _port(painter: QPainter, x: float, y: float, color: str) -> None:
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QPointF(x, y), _PORT_R, _PORT_R)


def paint_app_icon(painter: QPainter, variant: str = "studio") -> None:
    """Draws the icon into the S×S design grid."""
    painter.setRenderHint(QPainter.Antialiasing)
    _tile(painter)
    path = _p_path()
    if variant == "viewer":
        _stroke(painter, path, _GREEN)
        _port(painter, _STEM_X, _BOTTOM_Y, _GREEN)
        # play triangle inside the bowl
        cx, cy = (_STEM_X + _BOWL_RIGHT - 140) / 2 + 20, (_TOP_Y + _BOWL_BOTTOM) / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(_WHITE))
        triangle = QPolygonF([QPointF(cx - 55, cy - 70), QPointF(cx + 75, cy),
                              QPointF(cx - 55, cy + 70)])
        painter.drawPolygon(triangle)
    else:
        _stroke(painter, path, _BLUE)
        # bowl end: purple port on the P's right-hand curve; stem foot: green
        _port(painter, _BOWL_RIGHT - 20, (_TOP_Y + _BOWL_BOTTOM) / 2 + 40, _PURPLE)
        _port(painter, _STEM_X, _BOTTOM_Y, _GREEN)


def render_pixmap(size: int, variant: str = "studio") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.scale(size / S, size / S)
    paint_app_icon(painter, variant)
    painter.end()
    return pixmap


_ICONS: dict[str, QIcon] = {}


def app_icon(variant: str = "studio") -> QIcon:
    if variant not in _ICONS:
        icon = QIcon()
        for size in (16, 32, 64, 128, 256, 512, 1024):
            icon.addPixmap(render_pixmap(size, variant))
        _ICONS[variant] = icon
    return _ICONS[variant]


def viewer_icon() -> QIcon:
    return app_icon("viewer")


def icon_png_bytes(size: int = 180, variant: str = "viewer") -> bytes:
    """PNG bytes (favicon / apple-touch-icon of the phone page)."""
    from PySide6.QtCore import QBuffer, QIODevice
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    render_pixmap(size, variant).save(buffer, "PNG")
    return bytes(buffer.data())


def export_png(path: str, size: int = 512, variant: str = "studio") -> None:
    render_pixmap(size, variant).save(path, "PNG")


def export_iconset(folder: str, variant: str = "studio") -> None:
    """Writes an .iconset folder (macOS: iconutil -c icns <folder>)."""
    import os
    os.makedirs(folder, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        render_pixmap(size, variant).save(
            os.path.join(folder, f"icon_{size}x{size}.png"), "PNG")
        render_pixmap(size * 2, variant).save(
            os.path.join(folder, f"icon_{size}x{size}@2x.png"), "PNG")
