# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Main-process page: Kanban board + dashboard + card detail.

Drops decide actions:
  Backlog → In Progress   start the card (predecessor dialog when needed)
  Done → In Progress      run the card again
  In Progress → Backlog   stop a running card
  Done → Backlog     forget the card's result (and its successors')
Auto-advance (toggle) starts every card whose predecessors are Done."""

from __future__ import annotations

import asyncio
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QSplitter,
                               QToolButton, QVBoxLayout, QWidget)

from polytess.core.app_settings import AppSettings
from polytess.graph.board import (ACTIVE, DONE, FAILED, PENDING, QUEUED, STALE,
                                  BoardRunner)
from polytess.graph.inputs import apply_values, input_spec
from polytess.graph.model import Graph
from polytess.graph.processor import NodeStatus
from polytess.gui.icons import icon
from polytess.viewer import celebrations
from polytess.viewer.board_view import BoardView
from polytess.viewer.dashboard import Dashboard
from polytess.viewer.form import InputForm
from polytess.viewer.form_page import open_in_file_manager
from polytess.viewer.run_panel import RunPanel, format_duration


class _InputsDialog(QDialog):
    """The main flow's own inputs (Viewer form of the main process)."""

    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Process inputs")
        self.setMinimumSize(560, 420)
        self.spec = input_spec(graph)
        layout = QVBoxLayout(self)
        hint = QLabel("These values feed every card. Changing them marks "
                      "finished cards as outdated.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.form = InputForm(self.spec)
        layout.addWidget(self.form, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("flat")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton("Apply")
        ok.setObjectName("primary")
        ok.clicked.connect(self._accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _accept(self) -> None:
        if self.form.validate():
            return
        self.accept()


class BoardPage(QWidget):

    back_requested = Signal()

    def __init__(self, graph: Graph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.runner = BoardRunner(graph, on_change=self._on_change,
                                  on_progress=self._on_progress)
        self.runner.state.auto_advance = bool(
            AppSettings.instance().get("viewer_auto_advance", True))
        self._tasks: dict[str, asyncio.Task] = {}
        self._contexts: dict[str, object] = {}
        self._selected: str | None = None
        self._node_totals: dict[str, int] = {}
        self._node_done: dict[str, set] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        back = QToolButton()
        back.setIcon(icon("chevron-up", "text-light"))
        back.setAutoRaise(True)
        back.setToolTip("Back to start")
        back.clicked.connect(self.back_requested)
        head.addWidget(back)
        titles = QVBoxLayout()
        title = QLabel(graph.name)
        title.setObjectName("title")
        titles.addWidget(title)
        subtitle = QLabel(f"{os.path.basename(graph.path or '')} · "
                          f"{len(self.runner.spec.cards)} steps · "
                          f"{getattr(graph.lineage, 'tag', '')}")
        subtitle.setObjectName("subtitle")
        titles.addWidget(subtitle)
        head.addLayout(titles, 1)

        self.auto_box = QCheckBox("Auto-advance")
        self.auto_box.setToolTip("Start every card whose predecessors are done")
        self.auto_box.setChecked(self.runner.state.auto_advance)
        self.auto_box.toggled.connect(self._set_auto)
        head.addWidget(self.auto_box)
        inputs = QPushButton("Process inputs…")
        inputs.setObjectName("flat")
        inputs.clicked.connect(self._edit_inputs)
        head.addWidget(inputs)
        run_all = QPushButton("Run all")
        run_all.setObjectName("primary")
        run_all.clicked.connect(self.run_all)
        head.addWidget(run_all)
        reset_all = QPushButton("Reset")
        reset_all.setObjectName("flat")
        reset_all.setToolTip("Forget every result")
        reset_all.clicked.connect(self._reset_all)
        head.addWidget(reset_all)
        layout.addLayout(head)

        for problem in self.runner.spec.problems:
            warn = QLabel("⚠ " + problem)
            warn.setObjectName("error")
            layout.addWidget(warn)

        split = QSplitter(Qt.Horizontal)
        self.view = BoardView()
        self.view.card_clicked.connect(self._select)
        self.view.card_double_clicked.connect(self.start_card)
        self.view.card_dropped.connect(self._dropped)
        split.addWidget(self.view)
        self.dashboard = Dashboard()
        split.addWidget(self.dashboard)
        split.setStretchFactor(0, 1)
        vertical = QSplitter(Qt.Vertical)
        vertical.addWidget(split)
        layout.addWidget(vertical, 1)

        self.detail = QFrame()
        self.detail.setObjectName("card")
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(12, 8, 12, 8)
        detail_head = QHBoxLayout()
        self.detail_title = QLabel("Select a card")
        self.detail_title.setObjectName("section")
        detail_head.addWidget(self.detail_title, 1)
        self.detail_actions = QHBoxLayout()
        detail_head.addLayout(self.detail_actions)
        detail_layout.addLayout(detail_head)
        self.detail_text = QLabel("")
        self.detail_text.setObjectName("hint")
        self.detail_text.setWordWrap(True)
        detail_layout.addWidget(self.detail_text)
        self.run_panel = RunPanel()
        self.run_panel.pause_button.hide()      # cards run whole; stop + restart
        self.run_panel.stop_requested.connect(lambda: self.stop_card(self._selected))
        detail_layout.addWidget(self.run_panel, 1)
        vertical.addWidget(self.detail)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 2)
        vertical.setSizes([520, 300])

        self.view.set_spec(self.runner.spec)
        self._sync_all()

    # ---- state → view ------------------------------------------------------------- #

    def _sync_all(self, bounce_guid: str | None = None) -> None:
        for card in self.runner.spec.cards:
            cs = self.runner.state.card(card.guid)
            blocked = [c.title for c in self.runner.unfinished_predecessors(card.guid)]
            self.view.set_status(card.guid, cs.status, duration=cs.duration,
                                 error=cs.error, blocked_by=blocked)
        self.view.relayout(animate=True, bounce_guid=bounce_guid)
        self.dashboard.update_summary(self.runner.state.summary(self.runner.spec),
                                      self.runner.state.history)
        if self._selected:
            self._show_detail(self._selected)

    def _on_change(self, guid: str, status: str) -> None:
        card = self.runner.spec.card(guid)
        if status == DONE:
            self.view.celebrate_done(guid)
            cs = self.runner.state.card(guid)
            celebrations.toast(self.window(),
                               f"{card.title} finished · {format_duration(cs.duration or 0)}")
        elif status == FAILED:
            celebrations.toast(self.window(), f"{card.title} failed", accent="red")
        self._sync_all(bounce_guid=guid if status in (ACTIVE, DONE, FAILED, PENDING)
                       else None)
        if status == DONE and all(self.runner.status(c.guid) == DONE
                                  for c in self.runner.spec.cards):
            self.view.celebrate_all_done()
            celebrations.toast(self.window(), f"{self.graph.name}: everything done 🎉")

    def _on_progress(self, guid: str, node, status: NodeStatus) -> None:
        if status == NodeStatus.RUNNING:
            self._node_totals.setdefault(guid, 0)
        if status in (NodeStatus.SUCCESS, NodeStatus.FAIL):
            self._node_done.setdefault(guid, set()).add(getattr(node, "guid", ""))
        total = self._node_totals.get(guid) or 1
        done = len(self._node_done.get(guid, ()))
        item = self.view.items_by_guid.get(guid)
        if item is not None:
            item.progress = min(0.95, done / total)
            item.update()
        if guid == self._selected:
            self.run_panel.on_status(node, status)

    # ---- selection / detail ---------------------------------------------------------- #

    def _select(self, guid: str) -> None:
        self._selected = guid
        self._show_detail(guid)

    def _show_detail(self, guid: str) -> None:
        card = self.runner.spec.card(guid)
        cs = self.runner.state.card(guid)
        if card is None:
            return
        self.detail_title.setText(f"{card.title}  —  {cs.status}")
        lines = [card.description] if card.description else []
        if card.predecessors:
            lines.append("After: " + ", ".join(
                self.runner.spec.card(p).title for p in card.predecessors))
        node = self.runner.node(guid)
        bound = [f"{b.param} ← {b.value.display}" for b in node.inputs if b.is_bound]
        if bound:
            lines.append("Inputs: " + "; ".join(bound))
        outs = [f"{b.param} → {b.target.display}" for b in node.outputs if b.is_bound]
        if outs:
            lines.append("Outputs: " + "; ".join(outs))
        if cs.status == DONE and cs.duration:
            lines.append(f"Last run took {format_duration(cs.duration)}")
        if cs.error:
            lines.append("Error: " + cs.error)
        self.detail_text.setText("\n".join(lines))
        # actions
        while self.detail_actions.count():
            item = self.detail_actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if cs.status in (PENDING, STALE, FAILED, DONE):
            start = QPushButton("Run again" if cs.status == DONE else "Start")
            start.setObjectName("primary")
            start.clicked.connect(lambda: self.start_card(guid))
            self.detail_actions.addWidget(start)
        if cs.status == DONE:
            forget = QPushButton("Forget result")
            forget.setObjectName("flat")
            forget.clicked.connect(lambda: self._reset_card(guid))
            self.detail_actions.addWidget(forget)
        if cs.log and os.path.isfile(cs.log):
            show = QPushButton("Open log")
            show.setObjectName("flat")
            show.clicked.connect(lambda: open_in_file_manager(cs.log))
            self.detail_actions.addWidget(show)
        running = cs.status == ACTIVE
        self.run_panel.set_running(running)

    # ---- actions ---------------------------------------------------------------------- #

    def _set_auto(self, enabled: bool) -> None:
        self.runner.state.auto_advance = enabled
        self.runner.state.save()
        AppSettings.instance().set("viewer_auto_advance", enabled)
        AppSettings.instance().save()
        if enabled:
            self._advance()

    def _dropped(self, guid: str, column: str) -> None:
        status = self.runner.status(guid)
        if column == "active" and status in (PENDING, STALE, FAILED, DONE):
            self.start_card(guid)
            return
        if column == "backlog" and status == DONE:
            self._reset_card(guid)
            return
        if column == "backlog" and status == ACTIVE:
            self.stop_card(guid)
            return
        self.view.relayout(animate=True, bounce_guid=guid)   # slide back

    def start_card(self, guid: str) -> None:
        if guid in self._tasks and not self._tasks[guid].done():
            return
        if self.runner.spec.problems:
            QMessageBox.warning(self, "Board", "\n".join(self.runner.spec.problems))
            return
        if self.runner.status(guid) == DONE:
            self.runner.reset(guid)
        unfinished = self.runner.unfinished_predecessors(guid)
        unfinished = [c for c in unfinished if c.guid not in self._tasks
                      or self._tasks[c.guid].done()]
        plan_first = False
        if unfinished:
            names = ", ".join(c.title for c in unfinished)
            box = QMessageBox(self)
            box.setWindowTitle("Predecessors not finished")
            box.setText(f"Before this step, these must run first:\n{names}")
            box.setInformativeText("Run them in order now, or start only this step?")
            in_order = box.addButton("Run in order", QMessageBox.AcceptRole)
            only = box.addButton("Only this step", QMessageBox.DestructiveRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is in_order:
                plan_first = True
            elif box.clickedButton() is not only:
                self.view.relayout(animate=True, bounce_guid=guid)
                return
        self._select(guid)
        self.run_panel.begin(self.graph, f"Running {self.runner.spec.card(guid).title}…")
        self._node_totals[guid] = self._count_nodes(guid)
        self._node_done[guid] = set()

        async def job():
            try:
                if plan_first:
                    await self.runner.run_plan(guid)
                else:
                    status = await self.runner.run_card(guid)
                    if status == DONE and self.runner.state.auto_advance:
                        self._advance()
            except asyncio.CancelledError:
                pass

        task = asyncio.ensure_future(job())
        task.add_done_callback(lambda _t, g=guid: self._finished(g))
        self._tasks[guid] = task

    def _count_nodes(self, guid: str) -> int:
        try:
            node = self.runner.node(guid)
            path = node.resolve_file(self.graph.path or "", self.runner.workdir)
            sub = Graph.load(path)
            from polytess.graph.nodes import ExitNode, StartNode, TriggerNode
            return max(1, sum(1 for n in sub.nodes
                              if not isinstance(n, (StartNode, ExitNode, TriggerNode))))
        except Exception:
            return 1

    def _advance(self) -> None:
        """Auto-advance: start every ready card that is not running."""
        for card in self.runner.ready_cards():
            if card.guid in self._tasks and not self._tasks[card.guid].done():
                continue
            if self.runner.status(card.guid) == FAILED:
                continue                      # never auto-retry failures
            self.start_card(card.guid)

    def run_all(self) -> None:
        self.runner.state.auto_advance = True
        self.auto_box.setChecked(True)
        self._advance()

    def stop_card(self, guid: str | None) -> None:
        task = self._tasks.get(guid or "")
        if task is None or task.done():
            return
        task.cancel()
        self.run_panel.log.log("warning", "Stop requested")

    def _finished(self, guid: str) -> None:
        self._tasks.pop(guid, None)
        cs = self.runner.state.card(guid)
        if guid == self._selected:
            self.run_panel.finish(cs.status == DONE,
                                  "Stopped" if cs.error == "cancelled" else None)
        self._sync_all()

    def _reset_card(self, guid: str) -> None:
        self.runner.reset(guid)
        self._sync_all(bounce_guid=guid)

    def _reset_all(self) -> None:
        if any(not t.done() for t in self._tasks.values()):
            QMessageBox.information(self, "Board", "Stop running cards first.")
            return
        if QMessageBox.question(self, "Reset", "Forget every result of this process?") \
                == QMessageBox.Yes:
            self.runner.reset(None)
            self._sync_all()

    def _edit_inputs(self) -> None:
        dialog = _InputsDialog(self.graph, self)
        from polytess.viewer import presets
        last = presets.load_last(getattr(self.graph.lineage, "flow_id", ""))
        current = {f.name: (self.graph.variables.get(f.name) if f.kind == "variable"
                            else list(self.graph.lists.get(f.name).items))
                   for f in dialog.spec.fields}
        dialog.form.set_values(last or {})
        dialog.form.set_values(current)
        if dialog.exec() == QDialog.Accepted:
            values = dialog.form.values()
            apply_values(self.graph, values)
            presets.save_last(getattr(self.graph.lineage, "flow_id", ""), values)
            self.runner.state.capture(self.graph)
            self.runner.refresh_stale()
            self.runner.state.save()
            self._sync_all()

    # ---- closing ---------------------------------------------------------------------- #

    @property
    def is_running(self) -> bool:
        return any(not t.done() for t in self._tasks.values())

    def confirm_close(self) -> bool:
        if not self.is_running:
            return True
        if QMessageBox.question(self, "Run in progress",
                                "Cards are running. Stop them and leave?") \
                == QMessageBox.Yes:
            for guid in list(self._tasks):
                self.stop_card(guid)
            return True
        return False
