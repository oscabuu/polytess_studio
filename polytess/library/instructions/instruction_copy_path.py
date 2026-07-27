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


@meta(title="Copy", category="Files/Copy", icon="duplicate", color="blue",
      description="Copies a file or folder to a destination",
      keywords=("cp", "duplicate", "backup"))
class CopyPath(Instruction):

    def __init__(self, source: str = "", destination: str = "", overwrite: bool = True):
        super().__init__()
        self.source = PropertyGetPath(source)
        self.destination = PropertyGetPath(destination)
        self.overwrite = PropertyGetBool(overwrite)

    @property
    def title(self) -> str:
        return f"Copy {self.source} -> {self.destination}"

    async def run(self, ctx):
        src = ctx.resolve_path(self.source.get(ctx))
        dst = ctx.resolve_path(self.destination.get(ctx))
        overwrite = self.overwrite.get(ctx)
        if os.path.isdir(src):
            if os.path.isdir(dst) and overwrite:
                shutil.rmtree(dst)
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            if os.path.exists(dst) and not overwrite:
                raise FileExistsError(dst)
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copy2(src, dst)
        ctx.info(f"Copied {src} -> {dst}")
