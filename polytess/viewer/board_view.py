# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""The Kanban board itself — three columns of card items in a
QGraphicsScene, drag & drop between columns, animated re-layout.

The view knows statuses and geometry only; what a drop *means* (start,
stop, reset) is decided by the board page via ``card_dropped``."""

from __future__ import annotations

from PySide6.QtCore import (Property, QPointF, QRectF, Qt, Signal)
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsObject, QGraphicsScene,
                               QGraphicsView)

from polytess.graph.board import (ACTIVE, DONE, FAILED, PENDING, QUEUED, STALE,
                                  BoardSpec, Card)
from polytess.gui.theme import ACCENTS, COLORS
from polytess.viewer import celebrations
from polytess.viewer.run_panel import format_duration
from polytess.viewer.style import (STATUS_FILL, STATUS_LABEL, board_theme,
                                   status_colour, text_on)

COLUMNS = ("backlog", "active", "done")
COLUMN_TITLES = {"backlog": "Backlog", "active": "In Progress", "done": "Done"}
COLUMN_OF = {PENDING: "backlog", STALE: "backlog", FAILED: "backlog",
             QUEUED: "active", ACTIVE: "active", DONE: "done"}

COL_W, COL_GAP, PAD = 270.0, 18.0, 14.0        # COL_W = minimum column width
CARD_H, CARD_GAP = 118.0, 12.0
HEADER_H = 44.0


class CardItem(QGraphicsObject):

    clicked = Signal(str)
    double_clicked = Signal(str)
    dropped = Signal(str, float)        # guid, scene x of the card centre

    def __init__(self, card: Card):
        super().__init__()
        self.card = card
        self._slide_anim = None         # running slide, see celebrations.slide
        self.theme: dict | None = None  # set by the view
        self.width = COL_W - 2 * PAD    # set by the view (stretches with it)
        self.status = PENDING
        self.duration: float | None = None
        self.progress = 0.0             # 0..1 while active
        self.blocked_by: list[str] = []  # titles of unfinished predecessors
        self.error = ""
        self._glow = 0.0
        self._drag_origin: QPointF | None = None
        self._home = QPointF()
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(1)

    # ---- glow property (animated by celebrations.glow) ---------------------- #

    def get_glow(self) -> float:
        return self._glow

    def set_glow(self, value: float) -> None:
        self._glow = value
        self.update()

    glow = Property(float, get_glow, set_glow)

    # ---- geometry ---------------------------------------------------------------- #

    def boundingRect(self) -> QRectF:
        return QRectF(-4, -4, self.width + 8, CARD_H + 8)

    def set_width(self, width: float) -> None:
        if abs(width - self.width) > 0.5:
            self.prepareGeometryChange()
            self.width = width
            self.update()

    @property
    def draggable(self) -> bool:
        return self.status not in (ACTIVE, QUEUED)

    def set_home(self, pos: QPointF, bounce: bool) -> None:
        self._home = pos
        celebrations.slide(self, pos, bounce=bounce)

    # ---- painting ------------------------------------------------------------------ #

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width, CARD_H)
        theme = self.theme or board_theme()
        fill = QColor(status_colour(theme, self.status))
        if self._glow > 0:
            halo = QColor(ACCENTS["green"])
            halo.setAlphaF(0.55 * self._glow)
            painter.setPen(QPen(halo, 6))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 10, 10)
        painter.setPen(QPen(QColor(COLORS["border-active"] if self.isSelected()
                                   else theme["card_border"]), 1.5))
        painter.setBrush(QBrush(QColor(theme["card_fill"].get(self.status)
                                       or COLORS["bg-dark"])))
        painter.drawRoundedRect(rect, 8, 8)
        # accent stripe
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(0, 0, theme["stripe"], CARD_H), 3, 3)

        # title
        font = QFont(painter.font())
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ACCENTS["text"]))
        metrics = QFontMetrics(font)
        title = metrics.elidedText(self.card.title, Qt.ElideRight, int(self.width - 90))
        painter.drawText(QRectF(16, 8, self.width - 90, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         title)
        # status pill
        pill_font = QFont(painter.font())
        pill_font.setPointSize(9)
        pill_font.setBold(True)
        painter.setFont(pill_font)
        label = STATUS_LABEL[self.status]
        pill_w = QFontMetrics(pill_font).horizontalAdvance(label) + 14
        pill = QRectF(self.width - pill_w - 10, 10, pill_w, 17)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(pill, 8, 8)
        painter.setPen(QColor(text_on(status_colour(theme, self.status))))
        painter.drawText(pill, Qt.AlignCenter, label)

        # description
        body_font = QFont(painter.font())
        body_font.setPointSize(10)
        body_font.setBold(False)
        painter.setFont(body_font)
        painter.setPen(QColor(ACCENTS["text-light"]))
        text = self.card.description or self.card.file
        painter.drawText(QRectF(16, 32, self.width - 28, 34),
                         Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                         QFontMetrics(body_font).elidedText(text, Qt.ElideRight,
                                                            int((self.width - 28) * 2)))
        # footer line
        painter.setPen(QColor(ACCENTS["text-light"]))
        if self.status == ACTIVE:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(COLORS["bg-darkest"]))
            bar = QRectF(16, CARD_H - 22, self.width - 32, 6)
            painter.drawRoundedRect(bar, 3, 3)
            painter.setBrush(QColor(status_colour(theme, ACTIVE)))
            painter.drawRoundedRect(QRectF(bar.x(), bar.y(),
                                           max(6.0, bar.width() * self.progress), 6), 3, 3)
        else:
            footer = ""
            if self.status == DONE and self.duration:
                footer = f"✔ {format_duration(self.duration)}"
            elif self.status == FAILED:
                footer = "✖ " + (self.error.split(":", 1)[-1].strip()[:60] or "failed")
            elif self.status == STALE:
                footer = "inputs changed — run again"
            elif self.status == QUEUED:
                footer = "waiting for predecessors…"
            elif self.blocked_by:
                footer = "after: " + ", ".join(self.blocked_by)
            elif self.card.conditional:
                footer = "conditional step"
            painter.setPen(QColor(ACCENTS["red"] if self.status == FAILED
                                  else ACCENTS["text-light"]))
            painter.drawText(QRectF(16, CARD_H - 26, self.width - 28, 18),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             QFontMetrics(body_font).elidedText(footer, Qt.ElideRight,
                                                                int(self.width - 28)))

    # ---- interaction ---------------------------------------------------------------- #

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.clicked.emit(self.card.guid)
        if event.button() == Qt.LeftButton and self.draggable:
            self._drag_origin = event.scenePos() - self.pos()
            self.setZValue(10)
            self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._drag_origin is not None:
            self.setPos(event.scenePos() - self._drag_origin)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._drag_origin is not None:
            self._drag_origin = None
            self.setZValue(1)
            self.setCursor(Qt.OpenHandCursor)
            self.dropped.emit(self.card.guid, self.pos().x() + self.width / 2)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self.double_clicked.emit(self.card.guid)
        event.accept()


def column_x(index: int, col_w: float = COL_W) -> float:
    return index * (col_w + COL_GAP)


def column_at(x: float, col_w: float = COL_W) -> str:
    index = int(max(0, min(2, x // (col_w + COL_GAP))))
    return COLUMNS[index]


class BoardView(QGraphicsView):

    card_clicked = Signal(str)
    card_double_clicked = Signal(str)
    card_dropped = Signal(str, str)     # guid, column

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(COLORS["canvas"]))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.items_by_guid: dict[str, CardItem] = {}
        self._rows = 1
        self._col_w = COL_W
        self.theme = board_theme()

    def set_theme(self, name: str) -> None:
        self.theme = board_theme(name)
        for item in self.items_by_guid.values():
            item.theme = self.theme
            item.update()
        self.viewport().update()

    @property
    def column_width(self) -> float:
        """Columns share the viewport width (never narrower than COL_W)."""
        width = self.viewport().width() if self.isVisible() else self.width() - 16
        available = width - 2 * COL_GAP - 20      # room for the scrollbar
        return max(COL_W, available / 3.0)

    def _on_dropped(self, guid: str, x: float) -> None:
        self.card_dropped.emit(guid, column_at(x, self._col_w))

    # ---- building ---------------------------------------------------------------- #

    def set_spec(self, spec: BoardSpec) -> None:
        self._scene.clear()
        self.items_by_guid.clear()
        for card in spec.cards:
            item = CardItem(card)
            item.theme = self.theme
            item.clicked.connect(self.card_clicked)
            item.double_clicked.connect(self.card_double_clicked)
            item.dropped.connect(self._on_dropped)
            self._scene.addItem(item)
            self.items_by_guid[card.guid] = item
        self.relayout(animate=False)

    def relayout(self, animate: bool = True, bounce_guid: str | None = None) -> None:
        """Place every card in its column (by status, then by level and
        title). With *animate*, cards slide; the card named by
        *bounce_guid* (just dropped / just moved by auto-advance) bounces."""
        self._col_w = self.column_width
        card_w = self._col_w - 2 * PAD
        columns: dict[str, list[CardItem]] = {c: [] for c in COLUMNS}
        for item in self.items_by_guid.values():
            item.set_width(card_w)
            columns[COLUMN_OF[item.status]].append(item)
        rows = 1
        for index, column in enumerate(COLUMNS):
            items = sorted(columns[column],
                           key=lambda i: (i.card.level, i.card.title.lower()))
            rows = max(rows, len(items))
            for row, item in enumerate(items):
                target = QPointF(column_x(index, self._col_w) + PAD,
                                 HEADER_H + PAD + row * (CARD_H + CARD_GAP))
                if animate:
                    item.set_home(target, bounce=(item.card.guid == bounce_guid))
                else:
                    celebrations.stop_slide(item)
                    item._home = target
                    item.setPos(target)
        self._rows = rows
        height = HEADER_H + PAD * 2 + rows * (CARD_H + CARD_GAP)
        self._scene.setSceneRect(0, 0, 3 * self._col_w + 2 * COL_GAP,
                                 max(height, self.viewport().height() - 4, 300))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self.relayout(animate=False)

    def set_status(self, guid: str, status: str, **extra) -> None:
        item = self.items_by_guid.get(guid)
        if item is None:
            return
        item.status = status
        for key, value in extra.items():
            setattr(item, key, value)
        item.update()

    def celebrate_done(self, guid: str) -> None:
        item = self.items_by_guid.get(guid)
        if item is not None:
            celebrations.glow(item)

    def celebrate_all_done(self) -> None:
        rect = self._scene.sceneRect()
        celebrations.confetti(self._scene, rect.width(), rect.height())

    # ---- background: columns ----------------------------------------------------- #

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        scene_rect = self._scene.sceneRect()
        col_w = self._col_w
        for index, column in enumerate(COLUMNS):
            x = column_x(index, col_w)
            body = QRectF(x, 0, col_w, scene_rect.height())
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.theme["column_body"][column]))
            painter.drawRoundedRect(body, 10, 10)
            painter.setBrush(QColor(self.theme["column_head"][column]))
            painter.drawRoundedRect(QRectF(x, 0, col_w, HEADER_H), 10, 10)
            font = QFont(painter.font())
            font.setPointSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(self.theme["head_text"][column]))
            count = sum(1 for i in self.items_by_guid.values()
                        if COLUMN_OF[i.status] == column)
            painter.drawText(QRectF(x + PAD, 0, col_w - 2 * PAD, HEADER_H),
                             Qt.AlignLeft | Qt.AlignVCenter,
                             f"{COLUMN_TITLES[column]}   {count}")
