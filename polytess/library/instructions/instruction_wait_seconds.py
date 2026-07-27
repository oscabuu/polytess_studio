# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetAny, PropertyGetNumber, PropertyGetString


@meta(title="Wait Seconds", category="Flow/Wait Seconds", icon="clock", color="blue",
      description="Waits a certain amount of seconds",
      keywords=("wait", "time", "seconds", "cooldown", "timeout", "yield", "sleep"))
class WaitSeconds(Instruction):

    def __init__(self, seconds: float = 1.0):
        super().__init__()
        self.seconds = PropertyGetNumber(seconds)

    @property
    def title(self) -> str:
        return f"Wait {self.seconds} seconds"

    async def run(self, ctx):
        await self.wait_seconds(ctx, self.seconds.get(ctx))
