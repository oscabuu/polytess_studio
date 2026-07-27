# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta


@meta(title="Skip Next", category="Flow/Skip Next", icon="arrow-right", color="yellow",
      description="Skips the next N instructions in this list")
class SkipNext(Instruction):

    def __init__(self, count: int = 1):
        super().__init__()
        self.count = int(count)

    @property
    def title(self) -> str:
        return f"Skip next {self.count} instruction{'s' if self.count != 1 else ''}"

    async def run(self, ctx):
        self.jump(1 + max(0, int(self.count)))
