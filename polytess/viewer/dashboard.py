# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Statistics side panel of the board: progress ring, counters, time
spent / estimated remaining, success rate, history bars."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGridLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from polytess.graph.board import ACTIVE, DONE, FAILED, PENDING, QUEUED, STALE
from polytess.gui.theme import ACCENTS, COLORS
from polytess.viewer.run_panel import format_duration
from polytess.viewer.style import STATUS_FILL


class ProgressRing(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._text = "0 / 0"
        self.setFixedSize(150, 150)

    def set_progress(self, value: float, text: str) -> None:
        self._value = max(0.0, min(1.0, value))
        self._text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        pen = QPen(QColor(COLORS["bg-darkest"]), 12)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
        if self._value > 0:
            pen.setColor(QColor(ACCENTS["green"] if self._value >= 1.0
                                else COLORS["border-active"]))
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value))
        painter.setPen(QColor(ACCENTS["text"]))
        font = QFont(self.font())
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self._text)


class HistoryBars(QWidget):
    """Runs of the last 30 days: one bar per day (done green, failed red)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._days: list[tuple[int, int]] = [(0, 0)] * 30
        self.setMinimumHeight(54)
        self.setToolTip("Runs per day, last 30 days (green done, red failed)")

    def set_history(self, history: list[dict]) -> None:
        now = time.time()
        days = [[0, 0] for _ in range(30)]
        for item in history:
            started = item.get("started") or 0
            age = int((now - started) // 86400)
            if 0 <= age < 30:
                index = 29 - age
                days[index][0 if item.get("status") == DONE else 1] += 1
        self._days = [tuple(d) for d in days]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        width = self.width() / 30
        peak = max((d[0] + d[1] for d in self._days), default=1) or 1
        for i, (done, failed) in enumerate(self._days):
            x = i * width + 1
            base = self.height() - 2
            if done + failed == 0:
                painter.setBrush(QColor(COLORS["bg-darkest"]))
                painter.drawRect(QRectF(x, base - 3, width - 2, 3))
                continue
            h_done = (self.height() - 6) * done / peak
            h_fail = (self.height() - 6) * failed / peak
            painter.setBrush(QColor(STATUS_FILL[DONE]))
            painter.drawRect(QRectF(x, base - h_done, width - 2, h_done))
            painter.setBrush(QColor(STATUS_FILL[FAILED]))
            painter.drawRect(QRectF(x, base - h_done - h_fail, width - 2, h_fail))


class Dashboard(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(240)
        self.setMaximumWidth(300)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(6)

        title = QLabel("Overview")
        title.setObjectName("section")
        layout.addWidget(title)
        self.ring = ProgressRing()
        layout.addWidget(self.ring, 0, Qt.AlignHCenter)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self._counters: dict[str, QLabel] = {}
        rows = ((DONE, "Done"), (ACTIVE, "Running"), (QUEUED, "Queued"),
                (PENDING, "Backlog"), (STALE, "Outdated"), (FAILED, "Failed"))
        for row, (status, text) in enumerate(rows):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {STATUS_FILL[status]}; font-size: 14px;")
            name = QLabel(text)
            value = QLabel("0")
            value.setAlignment(Qt.AlignRight)
            value.setStyleSheet("font-weight: 600;")
            grid.addWidget(dot, row, 0)
            grid.addWidget(name, row, 1)
            grid.addWidget(value, row, 2)
            self._counters[status] = value
        layout.addLayout(grid)

        self._facts: dict[str, QLabel] = {}
        for key, text in (("time_spent", "Time spent"),
                          ("estimated_remaining", "Estimated remaining"),
                          ("success_rate", "Success rate"),
                          ("most_failing", "Most failing")):
            head = QLabel(text)
            head.setObjectName("hint")
            value = QLabel("–")
            value.setWordWrap(True)
            layout.addWidget(head)
            layout.addWidget(value)
            self._facts[key] = value

        hist_head = QLabel("Runs, last 30 days")
        hist_head.setObjectName("hint")
        layout.addWidget(hist_head)
        self.history = HistoryBars()
        layout.addWidget(self.history)
        layout.addStretch(1)

    def update_summary(self, summary: dict, history: list[dict]) -> None:
        counts = summary["counts"]
        self.ring.set_progress(summary["progress"],
                               f"{counts[DONE]} / {summary['total']}")
        for status, label in self._counters.items():
            label.setText(str(counts.get(status, 0)))
        self._facts["time_spent"].setText(format_duration(summary["time_spent"]))
        remaining = summary["estimated_remaining"]
        self._facts["estimated_remaining"].setText(
            format_duration(remaining) if remaining else
            ("nothing left" if summary["progress"] >= 1.0 else "no data yet"))
        rate = summary["success_rate"]
        self._facts["success_rate"].setText(
            f"{rate * 100:.0f} % of {summary['runs']} runs" if rate is not None
            else "no runs yet")
        self._facts["most_failing"].setText(summary["most_failing"] or "–")
        self.history.set_history(history)
