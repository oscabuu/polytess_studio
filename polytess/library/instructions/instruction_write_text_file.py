# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

import os
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Write Text File", category="Files/Write Text File", icon="file", color="yellow",
      description="Writes (or appends) text to a file; content supports variable sources",
      keywords=("save", "create", "text", "output"))
class WriteTextFile(Instruction):

    def __init__(self, path: str = "", content: str = "", append: bool = False):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.content = PropertyGetString(content)
        self.append = PropertyGetBool(append)

    @property
    def title(self) -> str:
        return f"Write text file {self.path}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        mode = "a" if self.append.get(ctx) else "w"
        with open(path, mode, encoding="utf-8") as fh:
            fh.write(self.content.get(ctx))
        ctx.info(f"Wrote {path}")
