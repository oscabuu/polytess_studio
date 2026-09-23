# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Assistant provider abstraction: Copilot bridge helpers, worker
branching and provider-aware status."""

import pytest

from polytess.core.app_settings import AppSettings
from polytess.gui.claude_agent_provider import (
    build_transcript_prompt as build_claude_agent_prompt)
from polytess.gui.copilot_provider import (build_transcript_prompt,
                                           enterprise_env)


@pytest.fixture(autouse=True)
def local_settings():
    AppSettings.reset(path="", use_command_server=False)
    yield
    AppSettings.reset(path="", use_command_server=False)


def test_enterprise_env():
    assert enterprise_env("") == {}
    env = enterprise_env("https://firma.ghe.com/")
    assert env == {"COPILOT_GH_HOST": "https://firma.ghe.com",
                   "GH_HOST": "https://firma.ghe.com"}


def test_transcript_prompt():
    single = [{"role": "user", "content": "hello"}]
    assert build_transcript_prompt(single) == "hello"

    multi = [{"role": "user", "content": "first"},
             {"role": "assistant", "content": "answer"},
             {"role": "user", "content": "second"}]
    prompt = build_transcript_prompt(multi)
    assert "User: first" in prompt and "Assistant: answer" in prompt
    assert prompt.rstrip().endswith("second")
    assert prompt.index("first") < prompt.index("second")


def test_claude_agent_transcript_prompt():
    single = [{"role": "user", "content": "hello"}]
    assert build_claude_agent_prompt(single) == "hello"

    multi = [{"role": "user", "content": "first"},
             {"role": "assistant", "content": "answer"},
             {"role": "user", "content": "second"}]
    prompt = build_claude_agent_prompt(multi)
    assert "User: first" in prompt and "Assistant: answer" in prompt
    assert prompt.index("first") < prompt.index("second")


def test_worker_reports_missing_sdk(qt_app):
    """Provider 'copilot' without the SDK installed fails with a helpful
    message instead of crashing."""
    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="copilot")
    from polytess.gui.code_assistant import AssistantWorker
    worker = AssistantWorker("system", [{"role": "user", "content": "hi"}])
    failures: list[str] = []
    worker.failed.connect(failures.append)
    worker.run()                      # synchronous — no thread needed
    assert failures and "github-copilot-sdk" in failures[0]


def test_worker_reports_missing_claude_agent_sdk(qt_app, monkeypatch):
    """Default provider without the SDK installed fails with a helpful
    message instead of crashing (simulated — a None entry in sys.modules
    makes the import raise ImportError regardless of the environment)."""
    import sys
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="claude_agent")
    from polytess.gui.code_assistant import AssistantWorker
    worker = AssistantWorker("system", [{"role": "user", "content": "hi"}])
    failures: list[str] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures and "claude-agent-sdk" in failures[0]


def test_provider_status_lines():
    from polytess.gui.code_assistant import provider_ready_status
    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="copilot",
                      github_host="https://firma.ghe.com")
    status = provider_ready_status()
    assert "Copilot" in status and "firma.ghe.com" in status

    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="claude_agent")
    assert "Claude Agent SDK" in provider_ready_status()


@pytest.fixture(scope="module")
def qt_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_copilot_permissions_scoped_to_workdir(tmp_path):
    """With a workdir, Copilot may read/write inside it only; shell and
    files elsewhere are denied. Without a workdir everything is denied."""
    from types import SimpleNamespace

    from polytess.gui.copilot_provider import permission_allowed

    lib = tmp_path / "lib"
    lib.mkdir()
    inside = SimpleNamespace(kind="read", path=str(lib / "block.py"),
                             resolved_path=None)
    relative = SimpleNamespace(kind="read", path="block.py",
                               resolved_path=None)
    outside = SimpleNamespace(kind="read", path=str(tmp_path / "secret"),
                              resolved_path=None)
    escape = SimpleNamespace(kind="write", file_name="../secret.py",
                             resolved_path=None)
    write_in = SimpleNamespace(kind="write", file_name="new_block.py",
                               resolved_path=str(lib / "new_block.py"))
    shell = SimpleNamespace(kind="shell", full_command="rm -rf /")

    assert permission_allowed(inside, str(lib))
    assert permission_allowed(relative, str(lib))
    assert permission_allowed(write_in, str(lib))
    assert not permission_allowed(outside, str(lib))
    assert not permission_allowed(escape, str(lib))
    assert not permission_allowed(shell, str(lib))
    assert not permission_allowed(inside, "")


def test_copilot_worker_passes_workdir(qt_app, monkeypatch):
    """The worker hands its workdir to the Copilot provider so the code
    assistant gets file access there (the flow assistant passes none)."""
    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="copilot")
    import polytess.gui.copilot_provider as provider
    from polytess.gui.code_assistant import AssistantWorker
    seen = {}

    def fake_stream(system_prompt, messages, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(provider, "stream_copilot", fake_stream)
    worker = AssistantWorker("sys", [{"role": "user", "content": "hi"}],
                             workdir="/tmp/lib")
    worker.run()
    assert seen["workdir"] == "/tmp/lib"
