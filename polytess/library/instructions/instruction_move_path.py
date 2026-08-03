# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
import shutil
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Move / Rename", category="Files/Move", icon="arrow-right", color="blue",
      description="Moves or renames a file or folder", keywords=("mv", "rename"))
class MovePath(Instruction):

    FIELD_HELP = {
        "source": "File or folder to move; relative paths resolve against "
                  "the working directory. The source must exist.",
        "destination": "New path (a rename when only the name changes); "
                       "relative paths resolve against the working "
                       "directory. Missing parent folders are created.",
    }

    def __init__(self, source: str = "", destination: str = ""):
        super().__init__()
        self.source = PropertyGetPath(source)
        self.destination = PropertyGetPath(destination)

    @property
    def title(self) -> str:
        return f"Move {self.source} -> {self.destination}"

    async def run(self, ctx):
        src = ctx.resolve_path(self.source.get(ctx))
        dst = ctx.resolve_path(self.destination.get(ctx))
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.move(src, dst)
        ctx.info(f"Moved {src} -> {dst}")
