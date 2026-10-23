# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Progress view of one run — current step, phase progress, elapsed time,
log, pause / stop. Used by the form page (whole flow) and by the board
(one card)."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from polytess.graph.nodes import StartNode, ExitNode, TriggerNode
from polytess.graph.processor import NodeStatus
from polytess.gui.log import LogPanel


def phase_names(graph) -> list[str]:
    """Sectioning convention: bool variables ``section_<n>_completed`` —
    one phase per section (plus the start chain)."""
    names = sorted(v.name for v in graph.variables
                   if v.name.startswith("section_") and v.name.endswith("_completed")
                   and v.type_id == "bool")
    return names


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


class RunPanel(QWidget):
    """Shows progress of a GraphProcessor run (node statuses via
    ``on_status``) — no knowledge of the graph beyond node names."""

    pause_requested = Signal(bool)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total = 0
        self._done: set[str] = set()
        self._started = 0.0
        self._running = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        head = QHBoxLayout()
        self.step_label = QLabel("Ready")
        self.step_label.setObjectName("section")
        head.addWidget(self.step_label, 1)
        self.time_label = QLabel("")
        self.time_label.setObjectName("hint")
        head.addWidget(self.time_label)
        layout.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.phase_label = QLabel("")
        self.phase_label.setObjectName("hint")
        layout.addWidget(self.phase_label)

        self.log = LogPanel()
        layout.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("flat")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.pause_requested)
        buttons.addWidget(self.pause_button)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.clicked.connect(self.stop_requested)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self.set_running(False)

    # ---- lifecycle -------------------------------------------------------------- #

    def begin(self, graph, title: str = "") -> None:
        self._total = sum(1 for n in graph.nodes
                          if not isinstance(n, (StartNode, ExitNode, TriggerNode)))
        self._done.clear()
        self._started = time.time()
        self.progress.setValue(0)
        self.step_label.setText(title or f"Running {graph.name}…")
        self.phase_label.setText("")
        self.log.clear()
        self.log.separator(title or f"Run: {graph.name}")
        self.set_running(True)
        self._timer.start()
        self._tick()

    def finish(self, ok: bool, message: str = "") -> None:
        self._timer.stop()
        self._tick()
        self.set_running(False)
        self.progress.setValue(100 if ok else self.progress.value())
        self.step_label.setText(message or ("Finished" if ok else "Failed"))
        self.log.separator("Run finished" if ok else "Run failed")

    def set_running(self, running: bool) -> None:
        self._running = running
        self.pause_button.setEnabled(running)
        self.pause_button.setChecked(False)
        self.stop_button.setEnabled(running)

    # ---- progress ---------------------------------------------------------------- #

    def on_status(self, node, status: NodeStatus) -> None:
        """Processor callback (any thread-safe context — Qt marshals the
        log; the labels are touched from the loop thread anyway)."""
        name = getattr(node, "name", "")
        if status == NodeStatus.RUNNING:
            self.step_label.setText(name)
        elif status in (NodeStatus.SUCCESS, NodeStatus.FAIL):
            self._done.add(getattr(node, "guid", name))
            if self._total:
                self.progress.setValue(int(100 * min(len(self._done), self._total)
                                           / self._total))
        if status == NodeStatus.FAIL:
            self.step_label.setText(f"Failed: {name}")

    def set_phase(self, index: int, total: int, name: str = "") -> None:
        self.phase_label.setText(f"Phase {index}/{total}" + (f" · {name}" if name else ""))

    def _tick(self) -> None:
        if self._started:
            self.time_label.setText(format_duration(time.time() - self._started))
