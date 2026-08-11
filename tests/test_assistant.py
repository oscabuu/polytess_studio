"""Code-editor Claude assistant: prompt building, registry knowledge,
code extraction and the chat panel (no network calls)."""

import os

import pytest

from polytess.core.app_settings import AppSettings
from polytess.gui.code_assistant import (build_registry_summary,
                                       build_system_prompt,
                                       build_user_message,
                                       extract_python_block)


@pytest.fixture(autouse=True)
def isolated_settings():
    yield
    AppSettings.reset(path="", use_command_server=False)


def test_registry_summary_knows_existing_blocks():
    import os
    summary = build_registry_summary()
    # company custom blocks appear when their files are present (dev machine)
    custom = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "custom_instructions",
        "instruction_combine_simpack_loads.py")
    if os.path.isfile(custom):
        assert "Combine Simpack Loads" in summary
        assert "Generate Modal Reduction File" in summary
    assert "On Variable Changed" in summary
    assert "Graph List Variable" in summary
    assert "date" in summary and "vector3" in summary and "transform" in summary


def test_system_prompt_contains_contract():
    prompt = build_system_prompt()
    for needle in ("@meta", "async def run", "persistent = True",
                   "PropertyGetString", "custom_library", "self.fire",
                   "report_color_primary", "Existing building blocks"):
        assert needle in prompt, needle


def test_user_message_with_file_context():
    plain = build_user_message("Wie schreibe ich einen Trigger?")
    assert plain == "Wie schreibe ich einen Trigger?"
    with_file = build_user_message("Fix this", "instruction_x.py", "code here")
    assert '<current_file name="instruction_x.py">' in with_file
    assert "code here" in with_file and with_file.endswith("Fix this")


def test_extract_python_block():
    assert extract_python_block("no code") == ""
    text = "Here:\n```python\nprint(1)\n```\nand\n```python\nprint(2)\n```\n"
    assert extract_python_block(text) == "print(2)\n"


def test_report_defaults_present():
    settings = AppSettings.reset(path="")
    assert settings.get("report_font") == "Arial"
    assert settings.get("report_color_primary").startswith("#")
    assert settings.get("assistant_provider") == "claude_agent"


def test_waiting_status_cycler_covers_all_phrases_before_repeating():
    from polytess.gui.code_assistant import WAITING_PHRASES, WaitingStatusCycler

    cycler = WaitingStatusCycler("Prefix")
    first = cycler.start()
    assert first.startswith("Prefix — ")
    seen = {first}
    for _ in range(len(WAITING_PHRASES) - 1):
        text = cycler.next()
        assert text not in seen        # no repeat within one full pass
        seen.add(text)
    assert len(seen) == len(WAITING_PHRASES)


def test_chat_panel_streaming_flow(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from polytess.gui.code_assistant import AssistantChatPanel
    from polytess.gui.code_editor import CodeEditorPanel

    editor = CodeEditorPanel(folder=str(tmp_path))
    panel = AssistantChatPanel(editor_panel=editor)

    # simulate a streamed answer without any network
    panel._history.append({"role": "user", "content": "q"})
    panel._transcript.append(("user", "q"))
    panel._transcript.append(("assistant", ""))
    panel._on_chunk("Hier ist der Code:\n```python\n")
    panel._on_chunk("print('hi')\n```")
    panel._on_finished("Hier ist der Code:\n```python\nprint('hi')\n```")
    assert panel.insert_button.isEnabled()
    assert panel._history[-1]["role"] == "assistant"

    # insert into the editor
    panel._insert_code()
    assert "print('hi')" in editor.edit.toPlainText()

    # apply replaces the whole editor content, undoably
    assert panel.apply_button.isEnabled()
    editor.edit.setPlainText("old content that should vanish")
    panel._apply_code()
    assert editor.edit.toPlainText() == "print('hi')\n"
    editor.edit.undo()
    assert editor.edit.toPlainText() == "old content that should vanish"

    # failure path keeps the UI consistent
    panel._transcript.append(("assistant", ""))
    panel._history.append({"role": "user", "content": "q2"})
    panel._on_failed("No API key configured")
    assert panel._transcript[-1][0] == "error"
    assert panel.send_button.isEnabled()


def test_custom_library_dir_honors_setting(tmp_path, monkeypatch):
    from polytess.library.custom import custom_library_dir

    monkeypatch.delenv("POLYTESS_CUSTOM_LIBRARY", raising=False)
    target = tmp_path / "my_blocks"
    AppSettings.reset(path="", custom_library_path=str(target))
    assert custom_library_dir() == str(target)
    assert target.is_dir()                       # created on demand

    # env var wins over the setting
    env_dir = tmp_path / "env_blocks"
    monkeypatch.setenv("POLYTESS_CUSTOM_LIBRARY", str(env_dir))
    assert custom_library_dir() == str(env_dir)


def test_code_assistant_worker_gets_custom_library_workdir(tmp_path,
                                                           monkeypatch):
    """The code assistant runs its worker rooted in the custom library
    (file tools); after an answer the library is hot-reloaded."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.delenv("POLYTESS_CUSTOM_LIBRARY", raising=False)
    library = tmp_path / "lib"
    AppSettings.reset(path="", custom_library_path=str(library))

    from polytess.gui.code_assistant import AssistantChatPanel
    panel = AssistantChatPanel()
    panel.input.setPlainText("write a block")
    started = {}

    import polytess.gui.code_assistant as module
    from PySide6.QtCore import QThread

    def fake_init(self, system_prompt, messages, parent=None, workdir=""):
        QThread.__init__(self)
        started["workdir"] = workdir

    monkeypatch.setattr(module.AssistantWorker, "__init__", fake_init)
    monkeypatch.setattr(module.AssistantWorker, "start", lambda self: None)
    panel.send()
    assert started.get("workdir") == str(library)

    # a file the assistant wrote lands in the registry after _on_finished
    (library / "instruction_assistant_made.py").write_text(
        "from polytess.core.instructions import Instruction\n"
        "from polytess.core.metadata import meta\n\n\n"
        "@meta(title='Assistant Made', category='Custom/Assistant Made')\n"
        "class AssistantMade(Instruction):\n"
        "    FIELD_HELP = {}\n\n"
        "    async def run(self, ctx):\n"
        "        ctx.info('hi')\n", encoding="utf-8")
    panel._on_finished("done, wrote instruction_assistant_made.py")
    from polytess.core.metadata import resolve_type
    assert resolve_type("AssistantMade") is not None


def test_chat_view_follows_streaming_text():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from polytess.gui.chat_view import ChatView

    view = ChatView()
    view.resize(400, 220)
    view.show()
    app.processEvents()
    bar = view.verticalScrollBar()

    def render(lines: int) -> None:
        view.set_transcript([
            ("user", "q"),
            ("assistant", "\n".join(f"line {i}" for i in range(lines)))])
        app.processEvents()

    def user_scroll_to(value: int) -> None:
        """Simulate the user dragging the scrollbar handle."""
        bar.setValue(value)
        bar.sliderMoved.emit(value)

    # streaming renders keep the view pinned to the end of the text
    for n in range(20, 121, 20):
        render(n)
    assert bar.value() >= bar.maximum() - 40

    # programmatic setValue alone must NOT detach (that was the v1.7.4
    # bug: async non-user valueChanged detached and froze the view)
    bar.setValue(0)
    render(125)
    assert bar.value() >= bar.maximum() - 40

    # a real user scroll detaches — and the reading position is
    # RESTORED on every re-render instead of jumping to the top
    middle = bar.maximum() // 2
    user_scroll_to(middle)
    render(130)
    assert abs(bar.value() - middle) <= 40
    render(135)
    assert abs(bar.value() - middle) <= 40

    # user scrolling back to the bottom re-attaches
    user_scroll_to(bar.maximum())
    render(140)
    assert bar.value() >= bar.maximum() - 40


def _enter_event(shift: bool = False):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    modifiers = Qt.ShiftModifier if shift else Qt.NoModifier
    return QKeyEvent(QEvent.KeyPress, Qt.Key_Return, modifiers)


def test_code_assistant_enter_sends_shift_enter_newline(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from polytess.gui.code_assistant import AssistantChatPanel
    from polytess.gui.code_editor import CodeEditorPanel

    editor = CodeEditorPanel(folder=str(tmp_path))
    panel = AssistantChatPanel(editor_panel=editor)
    sent = []
    panel.send = lambda: sent.append(True)

    assert panel.eventFilter(panel.input, _enter_event(shift=True)) is False
    assert sent == []          # Shift+Enter did not send — a newline instead

    assert panel.eventFilter(panel.input, _enter_event()) is True
    assert sent == [True]      # plain Enter sends


def test_flow_assistant_enter_sends_shift_enter_newline():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from polytess.gui.flow_assistant import FlowAssistantPanel

    panel = FlowAssistantPanel()
    sent = []
    panel.send = lambda: sent.append(True)

    assert panel.eventFilter(panel.input, _enter_event(shift=True)) is False
    assert sent == []
    assert panel.eventFilter(panel.input, _enter_event()) is True
    assert sent == [True]


def test_registry_summary_includes_field_shapes():
    """The code assistant's registry carries the full block shape:
    fields with kinds, choices and FIELD_HELP tooltips."""
    summary = build_registry_summary()
    assert "CreateFolder [Create Folder]" in summary
    assert "path: path — Directory to create" in summary
    assert "Property get-sources" in summary
    # flow registry too
    from polytess.graph.flow_builder import build_flow_registry_summary
    flow_summary = build_flow_registry_summary()
    assert "path: path — Directory to create" in flow_summary


def test_best_practices_file_seed_load_append(tmp_path, monkeypatch):
    import polytess.core.userdir as userdir
    monkeypatch.setattr(userdir, "user_dir", lambda: str(tmp_path))
    from polytess.gui.flow_assistant import (append_best_practice,
                                             best_practices_path,
                                             build_flow_system_prompt,
                                             extract_bestpractice_block,
                                             load_best_practices)

    path = best_practices_path()          # seeds from the shipped asset
    assert path == str(tmp_path / "flow_best_practices.md")
    content = load_best_practices()
    assert "# Flow best practices" in content

    lesson = extract_bestpractice_block(
        "Text\n```bestpractice\n- Always gate solver runs.\n```\n")
    assert lesson == "- Always gate solver runs."
    assert append_best_practice(lesson)
    assert "Always gate solver runs." in load_best_practices()

    prompt = build_flow_system_prompt()
    assert "Best practices (growing" in prompt
    assert "Always gate solver runs." in prompt

    # standing behavioral rules: admit gaps + section long flows
    assert "SAY SO" in prompt and "code assistant" in prompt
    assert "Sectioning long flows" in prompt
    assert "OnVariableChanged" in prompt
    assert "section_1_completed" in prompt


def test_flow_assistant_sees_open_flow():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from polytess.graph.flow_builder import build_flow
    from polytess.gui.flow_assistant import FlowAssistantPanel

    graph = build_flow({
        "name": "Open Flow",
        "nodes": [{"id": "a", "kind": "actions", "instructions": [
            {"type": "LogMessage", "params": {"message": "hi"}}]}],
        "edges": [{"from": "start", "to": "a"}],
    }).graph

    # without a provider: no context block
    assert FlowAssistantPanel()._current_flow_context() == ""
    # with a provider returning None (no open document): no context block
    assert FlowAssistantPanel(
        graph_provider=lambda: None)._current_flow_context() == ""

    panel = FlowAssistantPanel(graph_provider=lambda: graph)
    context = panel._current_flow_context()
    assert context.startswith('<current_flow name="Open Flow">')
    assert "LogMessage" in context and context.endswith("</current_flow>")
