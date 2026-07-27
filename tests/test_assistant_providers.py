# Copyright (c) 2026 Winthir Studios. All rights reserved.
"""Assistant provider abstraction: Copilot bridge helpers, worker
branching and provider-aware status."""

import pytest

from polytess.core.app_settings import AppSettings
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


def test_provider_status_lines():
    from polytess.gui.code_assistant import provider_ready_status
    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="copilot",
                      github_host="https://firma.ghe.com")
    status = provider_ready_status()
    assert "Copilot" in status and "firma.ghe.com" in status

    AppSettings.reset(path="", use_command_server=False,
                      assistant_provider="anthropic", anthropic_api_key="")
    import os
    had = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        assert "API key" in provider_ready_status()
    finally:
        if had is not None:
            os.environ["ANTHROPIC_API_KEY"] = had


@pytest.fixture(scope="module")
def qt_app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
