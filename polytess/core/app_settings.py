# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Application-wide settings (not workflow variables).

Persisted as JSON in ``~/.polytess/settings.json`` — shared by the studio and
headless runs. GUI-free; the settings dialog in the studio edits the same
singleton.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    # console commands run as: ssh <command_server> "cd ... && command".
    # Empty server or use_command_server=False -> plain local execution.
    "use_command_server": False,
    "command_server": "",
    "ssh_options": "-o BatchMode=yes -o ConnectTimeout=15",
    # solver profiles (MKS = multibody/Simpack, FEM = Abaqus). Each profile
    # defines the solver call and HOW it runs: locally or via ssh to <host>,
    # wrapped for the remote login shell (tcsh | bash | cmd for Windows
    # remotes). path_local/path_remote translate a shared-storage prefix
    # (e.g. P:\projects <-> /proj/projects) for cross-OS execution.
    "mks_command": "simpack-slv",
    "mks_use_ssh": False,
    "mks_host": "",
    "mks_shell": "tcsh",
    "mks_path_local": "",
    "mks_path_remote": "",
    "fem_command": "abaqus",
    "fem_use_ssh": False,
    "fem_host": "",
    "fem_shell": "tcsh",
    "fem_path_local": "",
    "fem_path_remote": "",
    # studio assistants (code editor + flow assistant). Provider:
    # "claude_agent" (Claude Agent SDK, auth via one-time 'claude login' —
    # no API key stored here) or "copilot" (GitHub Copilot SDK, uses the
    # user's Copilot login/subscription — works with GitHub Enterprise via
    # github_host, e.g. https://firma.ghe.com).
    "assistant_provider": "claude_agent",
    "assistant_model": "",
    "copilot_model": "claude-sonnet-4.5",
    "github_host": "",
    "github_token": "",
    # corporate defaults for generated reports/plots (readable from any
    # instruction via AppSettings.instance().get(...)). report_email is
    # the default notification recipient — Send Email falls back to it
    # when its "to" field is empty.
    "report_email": "",
    "report_font": "Arial",
    "report_font_size": 11,
    "report_color_primary": "#1f4e63",
    "report_color_secondary": "#519932",
    "report_color_accent": "#e9754c",
    # extra directories on sys.path — for custom_library modules (and any
    # in-studio Python execution) that import from your own local packages
    "python_include_paths": [],
    # custom-library folder override (empty = ~/.polytess/custom_library;
    # the POLYTESS_CUSTOM_LIBRARY env var wins over both)
    "custom_library_path": "",
}


class AppSettings:

    _instance: "AppSettings | None" = None

    def __init__(self, path: str | None = None):
        if path is None:
            from polytess.core.userdir import user_dir
            path = os.path.join(user_dir(), "settings.json")
        self.path = path
        self.values: dict[str, Any] = dict(DEFAULTS)
        self.load()

    @classmethod
    def instance(cls) -> "AppSettings":
        if cls._instance is None:
            cls._instance = AppSettings()
        return cls._instance

    @classmethod
    def reset(cls, path: str | None = None, **overrides) -> "AppSettings":
        """Replace the singleton (tests: pass path='' for a non-persistent
        instance plus explicit values)."""
        instance = AppSettings(path=path)
        instance.values.update(overrides)
        cls._instance = instance
        return instance

    # ---- persistence ------------------------------------------------------ #

    def load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for key in DEFAULTS:
                    if key in data:
                        self.values[key] = data[key]
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.values, fh, indent=2)

    # ---- access ------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value


_injected_python_paths: list[str] = []


def sync_python_include_paths() -> None:
    """Add ``python_include_paths`` to ``sys.path`` (idempotent) and drop
    previously-injected entries that were removed from the setting again.
    Called at startup and whenever the settings dialog saves — only ever
    touches paths this function itself added, never sys.path entries from
    anywhere else."""
    import sys
    global _injected_python_paths
    wanted = [p for p in (AppSettings.instance().get("python_include_paths") or []) if p]
    for path in _injected_python_paths:
        if path not in wanted and path in sys.path:
            sys.path.remove(path)
    for path in wanted:
        if path not in sys.path:
            sys.path.insert(0, path)
    _injected_python_paths = wanted
