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

    # failure path keeps the UI consistent
    panel._transcript.append(("assistant", ""))
    panel._history.append({"role": "user", "content": "q2"})
    panel._on_failed("No API key configured")
    assert panel._transcript[-1][0] == "error"
    assert panel.send_button.isEnabled()


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
