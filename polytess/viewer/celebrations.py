# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Feedback effects, in three levels (Settings → Celebrations):

- ``off``    nothing beyond plain layout changes
- ``subtle`` (default) smooth slide + playful bounce when a card lands
             in a column (user drag or auto-advance), short glow when a
             card becomes Done, toast with the duration
- ``full``   subtle + confetti when the whole process is Done

Rewards progress of the process, never click counts; nothing blocks."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import (QEasingCurve, QObject, QPointF, QPropertyAnimation,
                            QTimer, Qt)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QLabel

from polytess.core.app_settings import AppSettings
from polytess.gui.theme import ACCENTS

LEVELS = ("off", "subtle", "full")


def level() -> str:
    value = str(AppSettings.instance().get("viewer_celebrations") or "subtle")
    return value if value in LEVELS else "subtle"


def set_level(value: str) -> None:
    AppSettings.instance().set("viewer_celebrations", value)
    AppSettings.instance().save()


# ---- card motion ----------------------------------------------------------------- #

def _alive(item) -> bool:
    try:
        from shiboken6 import isValid
        return isValid(item)
    except ImportError:
        return True


def slide(item: QGraphicsObject, target: QPointF, bounce: bool = True,
          duration: int = 260) -> QPropertyAnimation | None:
    """Move *item* to *target*: immediate when off, eased otherwise, with
    an OutBack overshoot ("playful bounce") when *bounce* is set.

    The animation is held as a plain Python attribute (``_slide_anim``)
    and never as a Qt property: a property kept a QObject pointer to an
    animation that had already deleted itself (DeleteWhenStopped), and
    the next ``property()`` call on the card crashed the process."""
    if not _alive(item):
        return None
    stop_slide(item)
    if level() == "off" or item.pos() == target:
        item.setPos(target)
        return None
    animation = QPropertyAnimation(item, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(item.pos())
    animation.setEndValue(target)
    curve = QEasingCurve(QEasingCurve.OutBack if bounce else QEasingCurve.OutCubic)
    if bounce:
        curve.setOvershoot(1.6)
    animation.setEasingCurve(curve)
    item._slide_anim = animation

    def finished(anim=animation, target_item=item):
        if getattr(target_item, "_slide_anim", None) is anim:
            target_item._slide_anim = None

    animation.finished.connect(finished)
    animation.start()                         # KeepWhenStopped: we own it
    return animation


def stop_slide(item) -> None:
    """Abort a running slide so a direct setPos is not overridden by the
    animation's old target (e.g. after the view was resized)."""
    animation = getattr(item, "_slide_anim", None)
    item._slide_anim = None
    if animation is not None:
        try:
            animation.stop()
        except RuntimeError:                  # C++ side already gone
            pass


def glow(item, duration: int = 700) -> None:
    """Short highlight pulse on a card item (expects ``set_glow(float)``)."""
    if level() == "off" or not hasattr(item, "set_glow") or not _alive(item):
        return
    animation = QPropertyAnimation(item, b"glow", item)
    animation.setDuration(duration)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.OutQuad)
    animation.start(QPropertyAnimation.DeleteWhenStopped)


# ---- toast ------------------------------------------------------------------------------ #

class Toast(QLabel):
    """Small message that fades out at the bottom of its parent."""

    def __init__(self, parent, text: str, accent: str = "green",
                 timeout: int = 2600):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background: rgba(25, 25, 25, 230); color: {ACCENTS[accent]};"
            f" border: 1px solid {ACCENTS[accent]}; border-radius: 8px;"
            f" padding: 8px 18px; font-size: 14px; font-weight: 600;")
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        QTimer.singleShot(timeout, self.deleteLater)

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move((parent.width() - self.width()) // 2,
                  parent.height() - self.height() - 24)


def toast(parent, text: str, accent: str = "green") -> None:
    if level() != "off" and parent is not None:
        Toast(parent, text, accent)


# ---- confetti ------------------------------------------------------------------------- #

class Confetti(QGraphicsObject):
    """A burst of falling paper in a QGraphicsScene — ``full`` level only."""

    COLORS = ("green", "blue", "yellow", "pink", "teal", "purple", "red")

    def __init__(self, width: float, height: float, count: int = 140):
        super().__init__()
        self.setZValue(1000)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._w, self._h = width, height
        self._pieces = [{
            "x": random.uniform(0, width), "y": random.uniform(-height * 0.4, 0),
            "vx": random.uniform(-40, 40), "vy": random.uniform(120, 260),
            "size": random.uniform(5, 10), "angle": random.uniform(0, 360),
            "spin": random.uniform(-240, 240),
            "color": QColor(ACCENTS[random.choice(self.COLORS)]),
        } for _ in range(count)]
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def boundingRect(self):
        from PySide6.QtCore import QRectF
        return QRectF(0, 0, self._w, self._h)

    def _step(self) -> None:
        dt = 0.016
        self._t += dt
        alive = False
        for p in self._pieces:
            p["x"] += (p["vx"] + 30 * math.sin(self._t * 3 + p["size"])) * dt
            p["y"] += p["vy"] * dt
            p["angle"] += p["spin"] * dt
            if p["y"] < self._h + 20:
                alive = True
        self.update()
        if not alive or self._t > 4.5:
            self._timer.stop()
            self.hide()
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self)
            self.deleteLater()                # not inside this very slot

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setPen(QPen(Qt.NoPen))
        fade = 1.0 if self._t < 3.5 else max(0.0, 1.0 - (self._t - 3.5))
        for p in self._pieces:
            color = QColor(p["color"])
            color.setAlphaF(fade)
            painter.setBrush(color)
            painter.save()
            painter.translate(p["x"], p["y"])
            painter.rotate(p["angle"])
            painter.drawRect(-p["size"] / 2, -p["size"] / 4, p["size"], p["size"] / 2)
            painter.restore()


def confetti(scene, width: float, height: float) -> None:
    if level() == "full" and scene is not None:
        scene.addItem(Confetti(width, height))


class _Holder(QObject):
    pass
