# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta


@meta(title="Stop", category="Flow/Stop", icon="stop", color="red",
      description="Stops the current action list", keywords=("cancel", "abort", "exit"))
class Stop(Instruction):

    FIELD_HELP = {}

    async def run(self, ctx):
        self.stop_list()
