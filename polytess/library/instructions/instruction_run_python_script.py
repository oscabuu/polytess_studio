# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
import shlex
import sys
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetNumber, PropertyGetPath, PropertyGetString,
    PropertySetNumber, PropertySetString,
)
from polytess.library.instructions.instruction_run_command import RunCommand


@meta(title="Run Python Script", category="Process/Run Python Script", icon="terminal",
      color="red",
      description="Runs a Python script with the current interpreter "
                  "(e.g. post-processing scripts)",
      keywords=("script", "postprocessing", "python"))
class RunPythonScript(RunCommand):

    FIELD_HELP = {
        "script": "Python script file to execute with the current "
                  "interpreter; relative paths resolve against the "
                  "working directory.",
        "arguments": "Command-line arguments appended after the script "
                     "path (shell-like syntax).",
    }

    def __init__(self, script: str = "", arguments: str = ""):
        super().__init__()
        self.script = PropertyGetPath(script)
        self.arguments = PropertyGetString(arguments)

    @property
    def title(self) -> str:
        return f"Run Python {self.script} {self.arguments}"

    async def run(self, ctx):
        script = ctx.resolve_path(self.script.get(ctx))
        args = self.arguments.get(ctx)
        quoted = shlex.quote if os.name != "nt" else (lambda s: f'"{s}"' if " " in s else s)
        self.command = PropertyGetString(f"{quoted(sys.executable)} {quoted(script)} {args}".strip())
        await super().run(ctx)
