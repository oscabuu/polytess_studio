# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetList


@meta(title="Loop List", category="Variables/Loop List", icon="repeat", color="purple",
      description="Runs the nested actions once per list element; the element is "
                  "available as 'Loop Target' / {target}",
      keywords=("for", "foreach", "iterate", "doe"))
class LoopList(Instruction):
    LEGACY_ALIASES = {"list_name": "list"}

    FIELD_HELP = {
        "list": "List variable to iterate; the nested actions run once per "
                "element. A missing list only logs a warning and skips the "
                "loop.",
        "actions": "Instructions executed for each element; inside them the "
                   "current element is available as 'Loop Target' / "
                   "{target}.",
    }

    def __init__(self, list_name: str | list = ""):
        super().__init__()
        self.list = PropertyGetList(list_name)
        self.actions = InstructionList()

    @property
    def title(self) -> str:
        return f"Loop {self.list.display} ({len(self.actions)} actions)"

    async def run(self, ctx):
        items = self.list.get(ctx)
        if items is None:
            ctx.warning(f"Loop List: list {self.list.display} not found")
            return
        for element in list(items):
            if ctx.is_cancelled or (self._parent is not None and self._parent.is_cancelled):
                return
            await self.actions.run(ctx.child(target=element))
