# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetString


@meta(title="Log Message", category="Debug/Log Message", icon="message", color="teal",
      description="Writes a message to the log",
      parameters=(("Level", "debug / info / warning / error"),
                  ("Message", "The text to log (supports variable sources)")),
      keywords=("print", "console", "debug", "text"))
class LogMessage(Instruction):
    FIELD_CHOICES = {"level": ["debug", "info", "warning", "error"]}

    FIELD_HELP = {
        "level": "Severity of the log entry: 'debug' for diagnostics, "
                 "'info' (default) for normal output, 'warning' and "
                 "'error' for highlighted problems.",
        "message": "Text written to the log; supports variable sources, so "
                   "current values can be embedded.",
    }

    def __init__(self, message: str = "", level: str = "info"):
        super().__init__()
        self.level = level
        self.message = PropertyGetString(message)

    @property
    def title(self) -> str:
        return f"Log {self.level}: {self.message}"

    async def run(self, ctx):
        ctx.log(self.level, self.message.get(ctx))
