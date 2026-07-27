# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetAny, PropertyGetBool, PropertyGetNumber, PropertyGetPath,
    PropertyGetString, PropertySetAny, PropertySetBool, PropertySetNumber,
    PropertySetPath, PropertySetString,
)


@meta(title="Loop Range", category="Variables/Loop Range", icon="repeat", color="purple",
      description="Runs the nested actions for i = start .. stop (step); "
                  "i is available as 'Loop Target' / {target}",
      keywords=("for", "counter", "iterate"))
class LoopRange(Instruction):

    def __init__(self, start: float = 0.0, stop: float = 10.0, step: float = 1.0):
        super().__init__()
        self.start = PropertyGetNumber(start)
        self.stop = PropertyGetNumber(stop)
        self.step = PropertyGetNumber(step)
        self.actions = InstructionList()

    @property
    def title(self) -> str:
        return f"Loop {self.start} .. {self.stop} step {self.step}"

    async def run(self, ctx):
        start, stop, step = self.start.get(ctx), self.stop.get(ctx), self.step.get(ctx)
        if step == 0:
            ctx.warning("Loop Range: step is 0")
            return
        i = start
        while (step > 0 and i < stop) or (step < 0 and i > stop):
            if ctx.is_cancelled or (self._parent is not None and self._parent.is_cancelled):
                return
            value = int(i) if float(i).is_integer() else i
            await self.actions.run(ctx.child(target=value))
            i += step
