# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetAny, PropertyGetBool, PropertyGetNumber, PropertyGetPath,
    PropertyGetString, PropertySetAny, PropertySetBool, PropertySetNumber,
    PropertySetPath, PropertySetString,
)


@meta(title="Set Number", category="Variables/Set Number", icon="number", color="green",
      description="Stores a number into a variable", keywords=("assign", "value"))
class SetNumber(Instruction):

    FIELD_HELP = {
        "target": "Graph or global variable that receives the number.",
        "value": "The numeric value to store (default 0); can also be "
                 "read from another variable.",
    }

    def __init__(self, target=None, value: float = 0.0):
        super().__init__()
        self.target = target if target is not None else PropertySetNumber()
        self.value = PropertyGetNumber(value)

    @property
    def title(self) -> str:
        return f"Set {self.target} = {self.value}"

    async def run(self, ctx):
        self.target.set(self.value.get(ctx), ctx)
