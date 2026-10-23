# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Single-flow page: inputs form → run → result."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QToolButton, QVBoxLayout,
                               QWidget)

from polytess.core.context import Context
from polytess.graph.inputs import apply_values, input_spec
from polytess.graph.processor import GraphProcessor, NodeStatus
from polytess.gui.icons import icon
from polytess.viewer import celebrations, presets
from polytess.viewer.form import InputForm
from polytess.viewer.run_panel import RunPanel, format_duration, phase_names


def open_in_file_manager(path: str) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class FormPage(QWidget):
    """Form → run → result for one flow (no sub-workflow cards)."""

    back_requested = Signal()

    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.flow_id = getattr(graph.lineage, "flow_id", "") or ""
        self.spec = input_spec(graph)
        self._task: asyncio.Task | None = None
        self._ctx: Context | None = None
        self._processor: GraphProcessor | None = None
        self._started = 0.0
        self._last_values: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(10)

        head = QHBoxLayout()
        back = QToolButton()
        back.setIcon(icon("chevron-up", "text-light"))
        back.setToolTip("Back to start")
        back.setAutoRaise(True)
        back.clicked.connect(self.back_requested)
        head.addWidget(back)
        titles = QVBoxLayout()
        title = QLabel(graph.name)
        title.setObjectName("title")
        titles.addWidget(title)
        subtitle = QLabel(f"{os.path.basename(graph.path or '')} · "
                          f"{getattr(graph.lineage, 'tag', '')}")
        subtitle.setObjectName("subtitle")
        titles.addWidget(subtitle)
        head.addLayout(titles, 1)
        layout.addLayout(head)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_form_view())
        self.stack.addWidget(self._build_run_view())
        self.stack.addWidget(self._build_result_view())
        self._refresh_presets()
        last = presets.load_last(self.flow_id)
        if last:
            self.form.set_values(last)

    # ---- views ------------------------------------------------------------------- #

    def _build_form_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Preset"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self.preset_combo.currentIndexChanged.connect(self._load_preset)
        bar.addWidget(self.preset_combo)
        save = QPushButton("Save as…")
        save.setObjectName("flat")
        save.clicked.connect(self._save_preset)
        bar.addWidget(save)
        last = QPushButton("Last values")
        last.setObjectName("flat")
        last.setToolTip("Fill in the values of the most recent run")
        last.clicked.connect(lambda: self.form.set_values(presets.load_last(self.flow_id)))
        bar.addWidget(last)
        reset = QPushButton("Defaults")
        reset.setObjectName("flat")
        reset.setToolTip("Reset every field to the flow's own default")
        reset.clicked.connect(self._reset_defaults)
        bar.addWidget(reset)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.form = InputForm(self.spec)
        self.form.changed.connect(lambda: self.form.validate())
        layout.addWidget(self.form, 1)

        foot = QFrame()
        foot.setObjectName("card")
        foot_layout = QHBoxLayout(foot)
        foot_layout.addWidget(QLabel("Work folder"))
        self.workdir = QLineEdit(os.path.dirname(self.graph.path) if self.graph.path
                                 else os.getcwd())
        foot_layout.addWidget(self.workdir, 1)
        browse = QToolButton()
        browse.setIcon(icon("folder", "text-light"))
        browse.clicked.connect(self._pick_workdir)
        foot_layout.addWidget(browse)
        self.problem_label = QLabel("")
        self.problem_label.setObjectName("error")
        foot_layout.addWidget(self.problem_label)
        check = QPushButton("Check")
        check.setObjectName("flat")
        check.clicked.connect(self._check)
        foot_layout.addWidget(check)
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start)
        foot_layout.addWidget(self.start_button)
        layout.addWidget(foot)
        return view

    def _build_run_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        self.run_panel = RunPanel()
        self.run_panel.pause_requested.connect(self._pause)
        self.run_panel.stop_requested.connect(self.stop)
        layout.addWidget(self.run_panel, 1)
        return view

    def _build_result_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.result_title = QLabel("")
        self.result_title.setObjectName("title")
        layout.addWidget(self.result_title)
        self.result_subtitle = QLabel("")
        self.result_subtitle.setObjectName("subtitle")
        layout.addWidget(self.result_subtitle)
        self.outputs = QTableWidget(0, 2)
        self.outputs.setHorizontalHeaderLabels(["Result", "Value"])
        self.outputs.horizontalHeader().setStretchLastSection(True)
        self.outputs.verticalHeader().setVisible(False)
        self.outputs.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.outputs, 1)
        buttons = QHBoxLayout()
        open_folder = QPushButton("Open work folder")
        open_folder.setObjectName("flat")
        open_folder.clicked.connect(lambda: open_in_file_manager(self.workdir.text()))
        buttons.addWidget(open_folder)
        save_log = QPushButton("Save log…")
        save_log.setObjectName("flat")
        save_log.clicked.connect(self._save_log)
        buttons.addWidget(save_log)
        show_log = QPushButton("Show log")
        show_log.setObjectName("flat")
        show_log.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        buttons.addWidget(show_log)
        buttons.addStretch(1)
        again = QPushButton("Run again")
        again.setObjectName("flat")
        again.clicked.connect(self.start)
        buttons.addWidget(again)
        back = QPushButton("Back to inputs")
        back.setObjectName("primary")
        back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        buttons.addWidget(back)
        layout.addLayout(buttons)
        return view

    # ---- presets ------------------------------------------------------------------- #

    def _refresh_presets(self) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("(choose…)", "")
        for name in presets.list_presets(self.flow_id):
            self.preset_combo.addItem(name, name)
        self.preset_combo.blockSignals(False)

    def _load_preset(self, _index: int) -> None:
        name = self.preset_combo.currentData()
        if name:
            unknown = self.form.set_values(presets.load_preset(self.flow_id, name))
            if unknown:
                self.problem_label.setText("Preset has unknown fields: "
                                           + ", ".join(unknown))

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Name:")
        if ok and name.strip():
            presets.save_preset(self.flow_id, name.strip(), self.form.values())
            self._refresh_presets()
            self.preset_combo.setCurrentIndex(self.preset_combo.findData(name.strip()))

    def _reset_defaults(self) -> None:
        self.form.reset_defaults()
        self.form.validate()

    def _pick_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Work folder", self.workdir.text())
        if path:
            self.workdir.setText(path)

    # ---- running ------------------------------------------------------------------ #

    def _check(self) -> bool:
        problems = self.form.validate()
        self.problem_label.setText(f"{len(problems)} problem(s)" if problems else "")
        return not problems

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            return
        if not self._check():
            self.stack.setCurrentIndex(0)
            return
        values = self.form.values()
        self._last_values = values
        apply_values(self.graph, values)
        presets.save_last(self.flow_id, values)
        workdir = self.workdir.text().strip() or os.getcwd()
        os.makedirs(workdir, exist_ok=True)

        self.stack.setCurrentIndex(1)
        self.run_panel.begin(self.graph)
        self._started = time.time()
        self._phases = phase_names(self.graph)
        self._ctx = Context(graph=self.graph, workdir=workdir,
                            logger=self.run_panel.log.log)
        self._processor = GraphProcessor(self.graph, on_status=self._on_status)

        async def runner():
            try:
                await self._processor.run(self._ctx)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.run_panel.log.log("error", f"Run crashed: {exc.__class__.__name__}: {exc}")
                raise

        self._task = asyncio.ensure_future(runner())
        self._task.add_done_callback(self._on_done)

    def _on_status(self, node, status: NodeStatus) -> None:
        self.run_panel.on_status(node, status)
        if self._phases:
            completed = sum(1 for name in self._phases
                            if self.graph.variables.get(name) is True)
            self.run_panel.set_phase(min(completed + 1, len(self._phases)),
                                     len(self._phases))

    def _pause(self, paused: bool) -> None:
        if self._processor is None:
            return
        if paused:
            self._processor.pause()
        else:
            self._processor.resume()

    def stop(self) -> None:
        if not self.is_running:
            return
        if self._processor is not None and self._processor.is_paused:
            self._processor.resume()
        if self._ctx is not None:
            self._ctx.cancel()
        if self._processor is not None:
            self._processor.stop()
        self.run_panel.log.log("warning", "Stop requested")

    def _on_done(self, task: asyncio.Task) -> None:
        failed = bool(self._processor and self._processor.failed_nodes)
        cancelled = self._ctx is not None and self._ctx.is_cancelled
        crashed = (not task.cancelled()) and task.exception() is not None
        ok = not (failed or cancelled or crashed)
        duration = time.time() - self._started
        self.run_panel.finish(ok, "Stopped" if cancelled else None)
        self._task = None
        self._processor_failed = self._processor.failed_nodes if self._processor else []
        self._show_result(ok, cancelled, duration)
        if ok:
            celebrations.toast(self.window(), f"{self.graph.name} finished · "
                                              f"{format_duration(duration)}")

    def _show_result(self, ok: bool, cancelled: bool, duration: float) -> None:
        self.result_title.setText("Finished ✔" if ok else
                                  "Stopped" if cancelled else "Failed ✖")
        self.result_title.setStyleSheet(
            "color: #c2f771;" if ok else "color: #f1c437;" if cancelled else "color: #e9754c;")
        detail = f"Duration {format_duration(duration)}"
        if self._processor_failed:
            detail += " · failed: " + ", ".join(self._processor_failed)
        self.result_subtitle.setText(detail)
        self.outputs.setRowCount(0)
        for field in self.spec.outputs:
            row = self.outputs.rowCount()
            self.outputs.insertRow(row)
            self.outputs.setItem(row, 0, QTableWidgetItem(field.label))
            value = self.graph.variables.get(field.name) if field.kind == "variable" \
                else list(self.graph.lists.get(field.name).items)
            self.outputs.setItem(row, 1, QTableWidgetItem(str(value)))
        self.stack.setCurrentIndex(2)

    def _save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", os.path.join(self.workdir.text(),
                                           f"{self.graph.name}_run.log"),
            "Log files (*.log *.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.run_panel.log.view.toPlainText())

    def confirm_close(self) -> bool:
        if not self.is_running:
            return True
        answer = QMessageBox.question(self, "Run in progress",
                                      "A run is in progress. Stop it and leave?")
        if answer == QMessageBox.Yes:
            self.stop()
            return True
        return False
