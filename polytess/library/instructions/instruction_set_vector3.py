# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetVector3, PropertySetVector3,
                                    SetGraphVariable)


@meta(title="Set Vector3", category="Variables/Set Vector3", icon="axes",
      color="green", description="Stores an (x, y, z) vector into a variable",
      keywords=("assign", "position", "xyz", "vector"))
class SetVector3(Instruction):

    def __init__(self, target=None, value=None):
        super().__init__()
        self.target = target if target is not None \
            else PropertySetVector3(SetGraphVariable())
        self.value = PropertyGetVector3(value)

    @property
    def title(self) -> str:
        return f"Set {self.target} = {self.value}"

    async def run(self, ctx):
        self.target.set(self.value.get(ctx), ctx)
