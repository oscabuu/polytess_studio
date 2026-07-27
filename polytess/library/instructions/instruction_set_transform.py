# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetTransform, PropertySetTransform,
                                    SetGraphVariable)


@meta(title="Set Transform", category="Variables/Set Transform", icon="transform",
      color="teal",
      description="Stores a transform (position + rotation) into a variable",
      keywords=("assign", "pose", "placement", "position", "rotation"))
class SetTransform(Instruction):

    def __init__(self, target=None, value=None):
        super().__init__()
        self.target = target if target is not None \
            else PropertySetTransform(SetGraphVariable())
        self.value = PropertyGetTransform(value)

    @property
    def title(self) -> str:
        return f"Set {self.target} = {self.value}"

    async def run(self, ctx):
        self.target.set(self.value.get(ctx), ctx)
