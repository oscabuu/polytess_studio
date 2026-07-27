# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import glob as _glob
import os

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetString, PropertySetList


@meta(title="Find Files", category="Variables/Find Files", icon="search", color="blue",
      description="Finds files by glob pattern (e.g. results/**/*.odb) and stores "
                  "them in a list variable",
      keywords=("glob", "scan", "search", "directory"))
class FindFiles(Instruction):
    LEGACY_ALIASES = {"list_name": "target_list"}

    def __init__(self, pattern: str = "*", list_name: str = "files"):
        super().__init__()
        self.pattern = PropertyGetString(pattern)
        self.target_list = PropertySetList(list_name)

    @property
    def title(self) -> str:
        return f"Find files {self.pattern} -> {self.target_list.display}"

    async def run(self, ctx):
        pattern = self.pattern.get(ctx)
        if not os.path.isabs(pattern):
            pattern = os.path.join(ctx.workdir, pattern)
        matches = sorted(_glob.glob(pattern, recursive=True))
        lst = self.target_list.require(ctx, "path")
        if lst is None:
            ctx.warning("Find Files: no target list variable set")
            return
        lst.clear()
        for match in matches:
            lst.push(match)
        self.target_list.notify(ctx)
        ctx.info(f"Find Files: {len(matches)} match(es) for {pattern}")
