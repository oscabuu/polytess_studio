# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetAny, PropertySetList


@meta(title="Add To List", category="Variables/Add To List", icon="list", color="purple",
      description="Appends a value to a list variable")
class AddToList(Instruction):
    LEGACY_ALIASES = {"list_name": "list"}

    FIELD_HELP = {
        "list": "List variable the value is appended to; the element is "
                "pushed onto the end of the chosen graph/global list.",
        "value": "Value to append — a literal or any variable source; it is "
                 "added unchanged as a new list element.",
    }

    def __init__(self, list_name: str = "", value=None):
        super().__init__()
        self.list = PropertySetList(list_name)
        self.value = value if value is not None else PropertyGetAny()

    @property
    def title(self) -> str:
        return f"Add {self.value} to {self.list.display}"

    async def run(self, ctx):
        self.list.push(self.value.get(ctx), ctx)
