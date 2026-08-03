# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import GetGraphVariable, PropertyGetAny


@meta(title="Log Variable", category="Debug/Log Variable", icon="variable", color="teal",
      description="Writes name and current value of a graph/global variable to the log")
class LogVariable(Instruction):
    LEGACY_ALIASES = {"name": "value"}

    FIELD_HELP = {
        "value": "Graph or global variable to inspect; its name and current "
                 "value are written to the log at info level.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.value = PropertyGetAny(GetGraphVariable(name))

    @property
    def title(self) -> str:
        return f"Log Variable {self.value.display}"

    async def run(self, ctx):
        ctx.info(f"{self.value.display} = {self.value.get(ctx)!r}")
