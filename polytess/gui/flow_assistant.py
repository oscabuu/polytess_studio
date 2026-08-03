# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Claude-powered flow assistant — builds workflows from a process
description.

The user describes their engineering process in the chat; the agent designs
a flow in the simplified JSON schema (polytess.graph.flow_builder), checks the
registry summary for every building block it uses, and — when something is
missing — proposes a ready-to-paste prompt for the code assistant that
creates the missing blocks. "Insert flow" validates the JSON against the
real registry and opens the built graph as a new document tab.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                               QPlainTextEdit, QToolButton, QVBoxLayout,
                               QWidget)

from polytess.graph.flow_builder import (build_flow, build_flow_registry_summary,
                                       missing_blocks_prompt)
from polytess.gui.chat_view import ChatView
from polytess.gui.code_assistant import AssistantWorker
from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS

_FLOW_GUIDE = '''You are the flow assistant inside polytess Studio — a
node-based workflow tool
for engineering computations (Simpack, Abaqus, HPC jobs, file handling).
The user describes a process; you design a complete workflow for it.

## Output format
Describe your plan briefly, then put the COMPLETE flow in exactly ONE
```json block using this schema:

{
  "name": "<workflow name>",
  "variables": [{"name": "deck", "type": "string|number|bool|path|date",
                 "value": ...}],
  "lists":     [{"name": "paths", "type": "path", "items": []}],
  "nodes": [
    {"id": "prep", "kind": "actions", "name": "Optional display name",
     "instructions": [{"type": "<ClassName>", "params": {...}}]},
    {"id": "chk", "kind": "conditions", "mode": "and|or",
     "conditions": [{"type": "<ClassName>", "params": {...}}]},
    {"id": "br", "kind": "branch",
     "branches": [{"name": "case A", "conditions": [...],
                   "instructions": [...]}]},
    {"id": "trg", "kind": "trigger",
     "event": {"type": "<EventClassName>", "params": {...}}},
    {"id": "sub", "kind": "subworkflow", "file": "other.flow.json"}
  ],
  "edges": [
    {"from": "start", "to": "prep"},
    {"from": "chk", "port": "success", "to": "exit"},
    {"from": "chk", "port": "fail", "to": "prep"}
  ]
}

- "start" and "exit" nodes exist implicitly — reference them in edges.
- Conditions nodes have output ports "success" and "fail"; every other
  node has "out". Loops are built by wiring an edge back to an earlier
  node or with the loop instructions (LoopList, LoopRange, RepeatUntil —
  their body is the "actions"/"instructions" param).
- Param values: plain JSON values set constants. {"var": "name"} reads a
  graph variable, {"global": "name"} a global one (works for values,
  lists and tables alike), {"template": "MR_{deck}.inp"} builds a
  formatted string/path from variables, {"target": true} reads the loop
  target. For set:-fields (write targets) pass the variable name as a
  plain string, or {"global": "name"} for a global.
- Every "type" MUST be a class name from the registry below — check it.
  Declare every variable you reference.

## Missing building blocks
When the process needs a step that no registered block covers, still
design the flow and use a descriptive new class name for it. Then add a
section "### Missing building blocks" listing each of them and ONE
```text block containing a ready-to-send prompt for the CODE assistant
(it writes custom Instructions/Conditions/Events) — precise enough that
the resulting class (same class name!) makes your flow work.

## Rules
- ALWAYS answer in English, even when the user writes in German.
- Prefer existing blocks over inventing new ones; run console commands
  with RunCommand only when no dedicated block fits.
- Keep flows lean: one actions node per logical phase, conditions nodes
  for checks/gates, triggers only for genuinely event-driven starts.
'''


def build_flow_system_prompt() -> str:
    return _FLOW_GUIDE + "\n" + build_flow_registry_summary()


def extract_json_block(text: str) -> dict | None:
    """The last parseable ```json block of an answer."""
    for block in reversed(re.findall(r"```json\s*\n(.*?)```", text, re.DOTALL)):
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                return data
        except ValueError:
            continue
    return None


def extract_text_block(text: str) -> str:
    """The last ```text block (the proposed code-assistant prompt)."""
    blocks = re.findall(r"```text\s*\n(.*?)```", text, re.DOTALL)
    return blocks[-1].strip() if blocks else ""


class FlowAssistantPanel(QWidget):
    """Chat dock that designs flows. ``open_graph`` receives the built
    Graph; ``send_to_code_assistant`` (optional) receives a prompt text."""

    open_graph = Signal(object)              # Graph
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[dict] = []
        self._transcript: list[tuple[str, str]] = []
        self._streaming_text = ""
        self._worker: AssistantWorker | None = None
        self._system_prompt: str | None = None
        self._last_flow: dict | None = None
        self._last_prompt: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("<b>Flow Assistant</b>"))
        bar.addStretch(1)
        self.insert_button = QToolButton()
        self.insert_button.setIcon(icon("graph", "teal"))
        self.insert_button.setText(" Insert flow")
        self.insert_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.insert_button.setToolTip("Build the proposed flow and open it "
                                      "as a new document")
        self.insert_button.setEnabled(False)
        self.insert_button.clicked.connect(self._insert_flow)
        bar.addWidget(self.insert_button)
        self.prompt_button = QToolButton()
        self.prompt_button.setIcon(icon("edit", "yellow"))
        self.prompt_button.setToolTip("Copy the proposed prompt for the "
                                      "code assistant to the clipboard")
        self.prompt_button.setEnabled(False)
        self.prompt_button.clicked.connect(self._copy_prompt)
        bar.addWidget(self.prompt_button)
        clear_button = QToolButton()
        clear_button.setIcon(icon("trash", "text-light"))
        clear_button.setToolTip("Clear conversation")
        clear_button.clicked.connect(self.clear_chat)
        bar.addWidget(clear_button)
        layout.addLayout(bar)

        self.view = ChatView()
        layout.addWidget(self.view, 1)

        from polytess.gui.code_assistant import AttachmentBar
        self.attach_bar = AttachmentBar()
        layout.addWidget(self.attach_bar)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Describe your process — the agent designs the flow…  "
            "(Enter sends, Shift+Enter for a new line)")
        self.input.setFixedHeight(72)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        controls = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {ACCENTS['text-light']};")
        self.status.setWordWrap(True)
        controls.addWidget(self.status, 1)
        self.stop_button = QToolButton()
        self.stop_button.setIcon(icon("stop", "red"))
        self.stop_button.setToolTip("Stop the running request")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)
        controls.addWidget(self.stop_button)
        self.send_button = QToolButton()
        self.send_button.setIcon(icon("play", "green"))
        self.send_button.setText(" Send")
        self.send_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.send_button.clicked.connect(self.send)
        controls.addWidget(self.send_button)
        layout.addLayout(controls)

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self._render)

        from polytess.gui.code_assistant import provider_ready_status
        self._set_status(provider_ready_status())

    # ---- events ------------------------------------------------------------ #

    def eventFilter(self, obj, event):   # noqa: N802 (Qt API)
        from PySide6.QtCore import QEvent
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False        # Shift+Enter -> newline (default)
                self.send()
                return True
        return super().eventFilter(obj, event)

    # ---- chat --------------------------------------------------------------- #

    def send(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        question = self.input.toPlainText().strip()
        if not question:
            return
        self.input.setPlainText("")

        from polytess.gui.code_assistant import format_attachments
        attachments = self.attach_bar.take()
        user_message, shown = question, question
        if attachments:
            user_message = (format_attachments(attachments) + "\n\n"
                            + question)
            shown = question + "\n" + "  ".join(
                f"📎 {name}" for name, _ in attachments)

        self._history.append({"role": "user", "content": user_message})
        self._transcript.append(("user", shown))
        self._transcript.append(("assistant", ""))
        self._streaming_text = ""
        self._render()

        if self._system_prompt is None:
            self._system_prompt = build_flow_system_prompt()

        self._worker = AssistantWorker(self._system_prompt, list(self._history))
        self._worker.chunk.connect(self._on_chunk)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._render_timer.start()
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_status("Claude is designing the flow…")

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._set_status("Stopping…")

    def clear_chat(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        self._history.clear()
        self._transcript.clear()
        self._streaming_text = ""
        self._system_prompt = None        # re-read registry on next question
        self._last_flow = None
        self._last_prompt = ""
        self.insert_button.setEnabled(False)
        self.prompt_button.setEnabled(False)
        self._render()
        self._set_status("Conversation cleared.")

    # ---- worker callbacks ---------------------------------------------------- #

    def _on_chunk(self, text: str) -> None:
        self._streaming_text += text
        if self._transcript:
            self._transcript[-1] = ("assistant", self._streaming_text)

    def _on_finished(self, full_text: str) -> None:
        self._render_timer.stop()
        if self._transcript:
            self._transcript[-1] = ("assistant", full_text)
        self._history.append({"role": "assistant", "content": full_text})
        self._finish_request()
        self._evaluate_answer(full_text)

    def _on_failed(self, message: str) -> None:
        self._render_timer.stop()
        if self._transcript and self._transcript[-1] == ("assistant", ""):
            self._transcript.pop()
            self._history.pop()
        self._transcript.append(("error", message))
        self._finish_request()
        self._set_status("Error.")

    def _finish_request(self) -> None:
        self._render()
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._worker = None

    # ---- answer evaluation ----------------------------------------------------- #

    def _evaluate_answer(self, text: str) -> None:
        """Dry-build the proposed flow so the status line tells the truth
        (the agent's own registry check is advisory only)."""
        self._last_flow = extract_json_block(text)
        self._last_prompt = extract_text_block(text)
        if self._last_flow is None:
            self.insert_button.setEnabled(False)
            self.prompt_button.setEnabled(bool(self._last_prompt))
            self._set_status("Done (no flow block in the answer).")
            return
        result = build_flow(self._last_flow)
        self.insert_button.setEnabled(result.graph is not None)
        if result.missing:
            if not self._last_prompt:
                self._last_prompt = missing_blocks_prompt(
                    result.missing, str(self._last_flow.get("name", "")))
            self.prompt_button.setEnabled(True)
            self._set_status("Missing blocks: " + ", ".join(result.missing)
                             + " — a prompt for the code assistant is "
                               "ready (pencil button).")
        else:
            self.prompt_button.setEnabled(bool(self._last_prompt))
            n = len(result.graph.nodes) if result.graph else 0
            note = f" ({len(result.warnings)} notes)" if result.warnings \
                else ""
            self._set_status(f"Flow ready: {n} nodes — use \"Insert flow\" to "
                             f"open it as a new document.{note}")

    # ---- actions ----------------------------------------------------------------- #

    def _insert_flow(self) -> None:
        if self._last_flow is None:
            return
        result = build_flow(self._last_flow)
        if result.graph is None:
            self._set_status("Could not build the flow: "
                             + "; ".join(result.errors))
            return
        for warning in result.warnings:
            self.status_message.emit(f"Flow: {warning}")
        if result.missing:
            self._set_status("Inserted — missing blocks (nodes stay empty): "
                             + ", ".join(result.missing))
        else:
            self._set_status("Flow inserted.")
        self.open_graph.emit(result.graph)

    def _copy_prompt(self) -> None:
        if self._last_prompt:
            QApplication.clipboard().setText(self._last_prompt)
            self._set_status("Prompt copied — paste it into the code editor "
                             "chat (open the Code Editor, chat panel).")

    def _render(self) -> None:
        self.view.set_transcript(self._transcript)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
