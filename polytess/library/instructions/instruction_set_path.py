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


@meta(title="Set Path", category="Variables/Set Path", icon="folder", color="blue",
      description="Stores a file/directory path into a variable")
class SetPath(Instruction):

    FIELD_HELP = {
        "target": "Graph or global variable that receives the path.",
        "value": "The file or directory path to store; kept as entered "
                 "(resolution against the working directory happens "
                 "where the path is used).",
    }

    def __init__(self, target=None, value: str = ""):
        super().__init__()
        self.target = target if target is not None else PropertySetPath()
        self.value = PropertyGetPath(value)

    @property
    def title(self) -> str:
        return f"Set {self.target} = {self.value}"

    async def run(self, ctx):
        self.target.set(self.value.get(ctx), ctx)
