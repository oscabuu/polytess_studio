# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Delete everything in a folder except files matching a keep pattern
(the 'clean old HPC job output, keep the .inp' step)."""

from __future__ import annotations

import fnmatch
import os
import shutil

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetPath, PropertyGetString


@meta(title="Clean Folder", category="Files/Clean Folder", icon="trash", color="red",
      description="Deletes entries of a folder except those matching the keep "
                  "pattern (e.g. keep '*.inp'); optionally including subfolders",
      keywords=("clear", "purge", "job", "output", "except"))
class CleanFolder(Instruction):

    def __init__(self, folder: str = "", keep_pattern: str = "*.inp"):
        super().__init__()
        self.folder = PropertyGetPath(folder)
        self.keep_pattern = PropertyGetString(keep_pattern)   # ';'-separated globs
        self.delete_subfolders = PropertyGetBool(True)

    @property
    def title(self) -> str:
        return f"Clean {self.folder} (keep {self.keep_pattern})"

    async def run(self, ctx):
        folder = ctx.resolve_path(self.folder.get(ctx))
        if not os.path.isdir(folder):
            return
        patterns = [p.strip() for p in self.keep_pattern.get(ctx).split(";") if p.strip()]
        removed = 0
        for name in os.listdir(folder):
            if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                continue
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                if self.delete_subfolders.get(ctx):
                    shutil.rmtree(path)
                    removed += 1
            else:
                os.remove(path)
                removed += 1
        ctx.info(f"Clean Folder: removed {removed} entries in {folder}")
