# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Read Text File", category="Files/Read Text File", icon="file", color="yellow",
      description="Reads a text file into a variable")
class ReadTextFile(Instruction):

    FIELD_HELP = {
        "path": "Text file to read (UTF-8); relative paths resolve "
                "against the working directory. Fails if the file does "
                "not exist.",
        "target": "Graph or global string variable that receives the "
                  "complete file content.",
    }

    def __init__(self, path: str = "", target=None):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.target = target if target is not None else PropertySetString()

    @property
    def title(self) -> str:
        return f"Read {self.path} -> {self.target}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        with open(path, encoding="utf-8") as fh:
            self.target.set(fh.read(), ctx)
