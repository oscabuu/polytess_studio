# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta


@meta(title="Restart List", category="Flow/Restart List", icon="repeat", color="yellow",
      description="Jumps back to the first instruction of this list (loop)",
      keywords=("loop", "goto", "again"))
class RestartList(Instruction):

    async def run(self, ctx):
        if self._parent is not None:
            self.jump(-self._parent.running_index)
