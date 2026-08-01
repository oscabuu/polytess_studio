# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Claude-powered coding assistant for the in-studio code editor.

The assistant knows exactly how polytess building blocks are written (the
system prompt carries the full contract for Instructions / Conditions /
Events plus the three file templates) and it knows what already exists
(a registry summary of every registered type is appended). Requests run
in a worker thread and stream into the chat panel; the response's python
code block can be inserted into the editor directly.

Requires the ``anthropic`` package (``pip install polytess[ai]``) and an API
key — Settings dialog or the ``ANTHROPIC_API_KEY`` environment variable.
"""

from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit,
                               QToolButton, QVBoxLayout, QWidget)

from polytess.core.app_settings import AppSettings
from polytess.gui.chat_view import ChatView
from polytess.gui.icons import icon
from polytess.gui.theme import ACCENTS

# --------------------------------------------------------------------------- #
# prompt building
# --------------------------------------------------------------------------- #

_GUIDE = '''You are the coding assistant inside polytess Studio — a PySide6
node-based workflow tool
for engineering computations (Simpack, Abaqus, HPC jobs, file handling).
You help the user write custom Instructions, Conditions and Events in the
built-in code editor. The files live in ~/.polytess/custom_library/ as one
class per file (instruction_*.py / condition_*.py / event_*.py); saving in
the editor hot-reloads the class and it appears in the Add menus instantly.

## Contract for every building block
- Decorate the class with @meta(...) from polytess.core.metadata:
  title, category ("Custom/My Thing"), icon, color, description,
  keywords=(...), parameters=(("Field", "help"), ...).
  Icons include: terminal, file, folder, list, clock, check, cancel, search,
  repeat, bolt, variable, globe, edit, plus, minus, graph, filter, save,
  target, note, axes, transform, gear, string, number, toggle, diamond.
  Colors: red, green, blue, yellow, purple, pink, teal, text-light.
- The class MUST be constructible with no arguments; declare every field in
  __init__. Public fields (no "_" prefix) are serialized to the .flow.json
  and rendered in the inspector; "_"-prefixed attributes are runtime state.
- Field types and their inspector editors:
  * PropertyGetString/Number/Bool/Path/Date("default")  -> value slot whose
    source the user can switch (constant | graph variable | global variable |
    formatted template | ...). Read with .get(ctx).
  * PropertyGetList() / PropertyGetTable("name")        -> list/table slots
    (direct entry, graph or global variable). .get(ctx) returns a python
    list / the live table dict (None if missing).
  * PropertySetString/Number/Bool/Path/Any(...)         -> write target
    (graph/global variable); .set(value, ctx).
  * PropertySetList/Table("name")                       -> writable list or
    table variable (.push/.clear/.notify / .set/.ensure/.notify).
  * plain bool/int/float/str                            -> checkbox/spin/line.
  * FIELD_CHOICES = {"mode": ["a", "b"]}                -> dropdown for a
    plain str field.
  * InstructionList() / ConditionList()                 -> nested reorderable
    action/condition lists (like Loop List's body).
- Context (ctx) API: ctx.info/warning/error/debug(msg) write to the log;
  ctx.resolve_path(p); ctx.workdir; ctx.target (current loop element);
  ctx.graph_variables / ctx.graph_lists; ctx.globals.variables /
  ctx.globals.lists; ctx.is_cancelled.
- Instruction: `async def run(self, ctx)`. Raise an exception to fail the
  node (message is logged, node turns red, flow stops on that branch).
  Blocking work: `await asyncio.to_thread(fn, ...)`. Console commands:
  `from polytess.core.shell import run_console` — honors the global SSH
  command-server setting (tcsh-safe), returns (exit_code, output).
- App settings: `from polytess.core.app_settings import AppSettings` —
  `AppSettings.instance().get(key)`. For reports/plots use the corporate
  defaults: report_font, report_font_size, report_color_primary /
  _secondary / _accent (hex strings).
- Condition: `def run(self, ctx) -> bool` (synchronous); optional
  `@property def summary(self) -> str`.
- Event (trigger): `def start(self, fire, ctx)` arms it (call super().start
  first); call `self.fire(payload)` to fire — payload becomes the Loop
  Target of the triggered flow; `def stop(self)` disarms; class attribute
  `persistent = True` keeps the workflow alive listening.
- Dynamic titles: `@property def title(self) -> str` (Instructions/Events)
  — shown in the inspector list and node preview.

## File templates (working skeletons)
Instruction:
```python
from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetString


@meta(title="My Step", category="Custom/My Step", icon="terminal", color="teal",
      description="What this instruction does", keywords=("custom",))
class MyStep(Instruction):

    def __init__(self):
        super().__init__()
        self.text = PropertyGetString("hello")

    @property
    def title(self) -> str:
        return f"My Step {self.text}"

    async def run(self, ctx):
        ctx.info(f"My Step: {self.text.get(ctx)}")
```
Condition:
```python
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetNumber


@meta(title="My Check", category="Custom/My Check", icon="conditions",
      color="green", description="What this condition checks")
class MyCheck(Condition):

    def __init__(self):
        super().__init__()
        self.value = PropertyGetNumber(0)

    def run(self, ctx) -> bool:
        return self.value.get(ctx) > 0
```
Event:
```python
from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="My Trigger", category="Custom/My Trigger", icon="bolt",
      color="red", description="When this trigger fires")
class MyTrigger(Event):
    persistent = False

    def start(self, fire, ctx):
        super().start(fire, ctx)
        self.fire(None)
```

## Rules
- ALWAYS answer in English, even when the user writes in German.
- When creating or rewriting a file, put the COMPLETE file content in one
  ```python block so it can be inserted into the editor directly.
- Prefer reusing existing building blocks (below) over writing new ones —
  say so when one already covers the need.
- Match the codebase style: English docstrings/comments, 4-space indent.
'''


def build_registry_summary() -> str:
    """One line per registered type so the assistant knows what exists."""
    from polytess.core.conditions import Condition
    from polytess.core.events import Event
    from polytess.core.instructions import Instruction
    from polytess.core.metadata import get_meta, iter_subclasses
    from polytess.core.properties import PropertySource, SetSource
    from polytess.core.values import value_types

    def lines(base) -> list[str]:
        out = []
        for cls in sorted(iter_subclasses(base), key=lambda c: get_meta(c).category):
            m = get_meta(cls)
            description = (m.description or "").split(". ")[0][:120]
            out.append(f"- {m.title} ({cls.__name__}, {m.category}): {description}")
        return out

    parts = ["## Existing building blocks (already registered — do not duplicate)"]
    parts.append("### Instructions")
    parts += lines(Instruction)
    parts.append("### Conditions")
    parts += lines(Condition)
    parts.append("### Events")
    parts += lines(Event)
    parts.append("### Property get-sources")
    parts += lines(PropertySource)
    parts.append("### Property set-sources")
    parts += lines(SetSource)
    parts.append("### Value types: " + ", ".join(sorted(value_types())))
    return "\n".join(parts)


def build_system_prompt() -> str:
    return _GUIDE + "\n" + build_registry_summary()


def build_user_message(question: str, filename: str = "",
                       file_content: str = "") -> str:
    if file_content:
        return (f"<current_file name=\"{filename or 'untitled'}\">\n"
                f"{file_content}\n</current_file>\n\n{question}")
    return question


# --------------------------------------------------------------------------- #
# prompt attachments (the small "+" next to the input)
# --------------------------------------------------------------------------- #

MAX_ATTACHMENT_BYTES = 200_000


def read_attachment(path: str) -> tuple[str, str]:
    """(filename, text content) — refuses binary and oversized files."""
    size = os.path.getsize(path)
    if size > MAX_ATTACHMENT_BYTES:
        raise ValueError(f"{os.path.basename(path)} is too large "
                         f"({size // 1024} KB, limit "
                         f"{MAX_ATTACHMENT_BYTES // 1024} KB)")
    with open(path, "rb") as fh:
        raw = fh.read()
    if b"\x00" in raw:
        raise ValueError(f"{os.path.basename(path)} looks binary — only "
                         f"text files can be attached")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return os.path.basename(path), text


def format_attachments(attachments: list[tuple[str, str]]) -> str:
    """Attachment blocks prepended to the user message."""
    parts = []
    for name, text in attachments:
        parts.append(f'<attached_file name="{name}">\n{text}\n'
                     f"</attached_file>")
    return "\n\n".join(parts)


class AttachmentBar(QWidget):
    """'+' button plus a chip line listing the attached files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[tuple[str, str]] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.add_button = QToolButton()
        self.add_button.setIcon(icon("plus", "text-light"))
        self.add_button.setToolTip("Attach text files to the next message "
                                   "(.inp, .py, .csv, .flow.json, …)")
        self.add_button.clicked.connect(self._pick)
        layout.addWidget(self.add_button)
        self.chips = QLabel("")
        self.chips.setStyleSheet(f"color: {ACCENTS['text-light']};")
        self.chips.setWordWrap(True)
        layout.addWidget(self.chips, 1)
        self.clear_button = QToolButton()
        self.clear_button.setIcon(icon("cancel", "text-light"))
        self.clear_button.setToolTip("Remove all attachments")
        self.clear_button.clicked.connect(self.clear)
        self.clear_button.hide()
        layout.addWidget(self.clear_button)

    def _pick(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach files", "",
            "Text files (*.py *.inp *.json *.csv *.txt *.md *.yaml *.yml "
            "*.flow.json);;All files (*)")
        errors = []
        for path in paths:
            try:
                self.add_path(path)
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        if errors:
            QMessageBox.warning(self, "Attach files", "\n".join(errors))

    def add_path(self, path: str) -> None:
        name, text = read_attachment(path)
        self._attachments = [a for a in self._attachments if a[0] != name]
        self._attachments.append((name, text))
        self._refresh()

    def clear(self) -> None:
        self._attachments = []
        self._refresh()

    def take(self) -> list[tuple[str, str]]:
        """Attachments for the message being sent; the bar is cleared."""
        taken = self._attachments
        self.clear()
        return taken

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self._attachments]

    def _refresh(self) -> None:
        self.chips.setText("  ".join(f"📎 {name}" for name in self.names))
        self.clear_button.setVisible(bool(self._attachments))


def resolve_api_key() -> str:
    key = str(AppSettings.instance().get("anthropic_api_key") or "").strip()
    return key or os.environ.get("ANTHROPIC_API_KEY", "").strip()


def extract_python_block(text: str) -> str:
    """The last ```python fenced block of an assistant answer ('' if none)."""
    blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
    return blocks[-1].rstrip() + "\n" if blocks else ""


# --------------------------------------------------------------------------- #
# streaming worker
# --------------------------------------------------------------------------- #

class AssistantWorker(QThread):
    """Runs one streaming Claude request off the GUI thread."""

    chunk = Signal(str)
    finished_ok = Signal(str)     # full response text
    failed = Signal(str)

    def __init__(self, system_prompt: str, messages: list[dict], parent=None):
        super().__init__(parent)
        self._system = system_prompt
        self._messages = messages
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:   # noqa: C901
        provider = str(AppSettings.instance().get("assistant_provider")
                       or "anthropic")
        if provider == "copilot":
            self._run_copilot()
            return
        try:
            import anthropic
        except ImportError:
            self.failed.emit("The 'anthropic' package is not installed — "
                             "run: .venv/bin/python -m pip install anthropic")
            return
        key = resolve_api_key()
        if not key:
            self.failed.emit("No API key configured — set it in Settings "
                             "(gear icon) or export ANTHROPIC_API_KEY.")
            return
        model = str(AppSettings.instance().get("assistant_model")
                    or "claude-opus-4-8")
        client = anthropic.Anthropic(api_key=key)
        parts: list[str] = []
        try:
            with client.messages.stream(
                model=model,
                max_tokens=32000,
                thinking={"type": "adaptive"},
                system=[{
                    "type": "text",
                    "text": self._system,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=self._messages,
            ) as stream:
                for text in stream.text_stream:
                    if self._cancelled:
                        break
                    parts.append(text)
                    self.chunk.emit(text)
        except anthropic.AuthenticationError:
            self.failed.emit("Authentication failed — check the API key "
                             "in Settings.")
            return
        except anthropic.RateLimitError:
            self.failed.emit("Rate limited — wait a moment and try again.")
            return
        except anthropic.APIConnectionError:
            self.failed.emit("Network error — could not reach the Claude API.")
            return
        except anthropic.APIStatusError as exc:
            self.failed.emit(f"API error {exc.status_code}: {exc.message}")
            return
        except Exception as exc:   # worker thread must never crash the app
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")
            return
        self.finished_ok.emit("".join(parts))

    def _run_copilot(self) -> None:
        """One streaming request through the GitHub Copilot SDK."""
        from polytess.gui.copilot_provider import stream_copilot
        settings = AppSettings.instance()
        try:
            text = stream_copilot(
                self._system, self._messages,
                model=str(settings.get("copilot_model") or "gpt-5"),
                github_host=str(settings.get("github_host") or ""),
                github_token=str(settings.get("github_token") or ""),
                on_chunk=self.chunk.emit,
                is_cancelled=lambda: self._cancelled)
        except RuntimeError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:   # worker thread must never crash the app
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")
            return
        self.finished_ok.emit(text)


def provider_ready_status() -> str:
    """Status-line text describing the active assistant provider."""
    settings = AppSettings.instance()
    if str(settings.get("assistant_provider") or "anthropic") == "copilot":
        host = str(settings.get("github_host") or "").strip()
        where = host or "github.com"
        return (f"Ready — GitHub Copilot via {where} "
                f"({settings.get('copilot_model')}).")
    if resolve_api_key():
        return "Ready."
    return ("No API key — set it in Settings (gear icon) or export "
            "ANTHROPIC_API_KEY.")


# --------------------------------------------------------------------------- #
# chat panel
# --------------------------------------------------------------------------- #

class AssistantChatPanel(QWidget):
    """Chat dock next to the code editor. ``editor_panel`` provides the
    current file (context) and receives inserted code."""

    def __init__(self, editor_panel=None, parent=None):
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._history: list[dict] = []       # [{"role", "content"}]
        self._transcript: list[tuple[str, str]] = []   # (role, text) for display
        self._streaming_text = ""
        self._worker: AssistantWorker | None = None
        self._system_prompt: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        bar = QHBoxLayout()
        title = QLabel("<b>Claude Assistant</b>")
        bar.addWidget(title)
        bar.addStretch(1)
        self.insert_button = QToolButton()
        self.insert_button.setIcon(icon("edit", "teal"))
        self.insert_button.setToolTip("Insert the last python code block "
                                      "into the editor")
        self.insert_button.setEnabled(False)
        self.insert_button.clicked.connect(self._insert_code)
        bar.addWidget(self.insert_button)
        clear_button = QToolButton()
        clear_button.setIcon(icon("trash", "text-light"))
        clear_button.setToolTip("Clear conversation")
        clear_button.clicked.connect(self.clear_chat)
        bar.addWidget(clear_button)
        layout.addLayout(bar)

        self.view = ChatView()
        layout.addWidget(self.view, 1)

        self.attach_bar = AttachmentBar()
        layout.addWidget(self.attach_bar)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Ask about instructions, conditions, events…  "
            "(Enter sends, Shift+Enter for a new line)")
        self.input.setFixedHeight(64)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)

        controls = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {ACCENTS['text-light']};")
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

        # throttle re-rendering while streaming
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self._render)

        self._set_status(provider_ready_status())

    # ---- events -------------------------------------------------------------- #

    def eventFilter(self, obj, event):   # noqa: N802 (Qt API)
        from PySide6.QtCore import QEvent
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False        # Shift+Enter -> newline (default)
                self.send()
                return True
        return super().eventFilter(obj, event)

    # ---- chat ----------------------------------------------------------------- #

    def send(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        question = self.input.toPlainText().strip()
        if not question:
            return
        self.input.setPlainText("")

        filename, content = "", ""
        panel = self._editor_panel
        if panel is not None and getattr(panel, "_path", None):
            filename = os.path.basename(panel._path)
            content = panel.edit.toPlainText()
        user_message = build_user_message(question, filename, content)
        attachments = self.attach_bar.take()
        shown = question
        if attachments:
            user_message = (format_attachments(attachments) + "\n\n"
                            + user_message)
            shown = question + "\n" + "  ".join(
                f"📎 {name}" for name, _ in attachments)

        self._history.append({"role": "user", "content": user_message})
        self._transcript.append(("user", shown))
        self._transcript.append(("assistant", ""))
        self._streaming_text = ""
        self._render()

        if self._system_prompt is None:
            self._system_prompt = build_system_prompt()

        self._worker = AssistantWorker(self._system_prompt, list(self._history))
        self._worker.chunk.connect(self._on_chunk)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._render_timer.start()
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_status("Claude is answering…")

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
        self._system_prompt = None       # re-read registry on next question
        self.insert_button.setEnabled(False)
        self._render()
        self._set_status("Conversation cleared.")

    # ---- worker callbacks ------------------------------------------------------ #

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
        self.insert_button.setEnabled(bool(extract_python_block(full_text)))
        self._set_status("Done.")

    def _on_failed(self, message: str) -> None:
        self._render_timer.stop()
        if self._transcript and self._transcript[-1] == ("assistant", ""):
            self._transcript.pop()
            self._history.pop()          # drop the unanswered user turn
        self._transcript.append(("error", message))
        self._finish_request()
        self._set_status("Error.")

    def _finish_request(self) -> None:
        self._render()
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._worker = None

    # ---- rendering -------------------------------------------------------------- #

    def _render(self) -> None:
        self.view.set_transcript(self._transcript)

    def _insert_code(self) -> None:
        """Insert the last python block at the editor cursor (replaces the
        selection if there is one)."""
        if self._editor_panel is None:
            return
        for role, text in reversed(self._transcript):
            if role == "assistant":
                code = extract_python_block(text)
                if code:
                    self._editor_panel.edit.insertPlainText(code)
                    self._editor_panel.edit.setFocus()
                return

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
