# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Format a list variable as a text block (n items per line) — e.g. Abaqus
node lists with 8 values per line."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetList, PropertySetString


@meta(title="Format Value List", category="Text/Format Value List", icon="list",
      color="teal",
      description="Joins the elements of a list into a text block with "
                  "a fixed number of items per line (Abaqus node lists)",
      keywords=("join", "nodes", "block", "lines"))
class FormatValueList(Instruction):
    LEGACY_ALIASES = {"list_name": "list"}

    def __init__(self, list_name: str | list = "", items_per_line: int = 8,
                 separator: str = ", "):
        super().__init__()
        self.list = PropertyGetList(list_name)
        self.items_per_line = items_per_line
        self.separator = separator
        self.target = PropertySetString()

    @property
    def title(self) -> str:
        return f"Format {self.list.display} " \
               f"({self.items_per_line}/line) -> {self.target}"

    async def run(self, ctx):
        values = self.list.get(ctx)
        if values is None:
            raise ValueError(f"list {self.list.display} not found")
        per_line = max(1, int(self.items_per_line))

        def fmt(value):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)

        items = [fmt(v) for v in values]
        lines = [self.separator.join(items[i:i + per_line])
                 for i in range(0, len(items), per_line)]
        self.target.set("\n".join(lines), ctx)
