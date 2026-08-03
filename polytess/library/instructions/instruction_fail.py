# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetAny, PropertyGetNumber, PropertyGetString


@meta(title="Fail", category="Flow/Fail", icon="cancel", color="red",
      description="Raises an error — marks the node as failed and stops the list")
class Fail(Instruction):

    FIELD_HELP = {
        "message": "Error text raised when this step runs (default "
                   "'Failed'); it marks the node as failed and stops the "
                   "instruction list.",
    }

    def __init__(self, message: str = "Failed"):
        super().__init__()
        self.message = PropertyGetString(message)

    @property
    def title(self) -> str:
        return f"Fail: {self.message}"

    async def run(self, ctx):
        raise RuntimeError(self.message.get(ctx))
