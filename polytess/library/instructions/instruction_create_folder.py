# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Create Folder", category="Files/Create Folder", icon="folder", color="blue",
      description="Creates a directory (including parents) if it does not exist",
      keywords=("mkdir", "directory", "makedirs"))
class CreateFolder(Instruction):

    def __init__(self, path: str = ""):
        super().__init__()
        self.path = PropertyGetPath(path)

    @property
    def title(self) -> str:
        return f"Create folder {self.path}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            ctx.info(f"Created folder {path}")
