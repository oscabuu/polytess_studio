# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertySetList


@meta(title="Clear List", category="Variables/Clear List", icon="list", color="purple",
      description="Removes all elements from a list variable")
class ClearList(Instruction):
    LEGACY_ALIASES = {"list_name": "list"}

    def __init__(self, list_name: str = ""):
        super().__init__()
        self.list = PropertySetList(list_name)

    @property
    def title(self) -> str:
        return f"Clear list {self.list.display}"

    async def run(self, ctx):
        self.list.clear(ctx)
