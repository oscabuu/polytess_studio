# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Sort a table variable by a column."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertySetTable


@meta(title="Sort Table", category="Tables/Sort Table", icon="list", color="pink",
      description="Sorts the rows of a table variable by a column "
                  "(numeric when possible)")
class SortTable(Instruction):
    LEGACY_ALIASES = {"table_name": "table"}

    def __init__(self, table_name: str = "", column: str = "", ascending: bool = True):
        super().__init__()
        self.table = PropertySetTable(table_name)
        self.column = column
        self.ascending = ascending

    @property
    def title(self) -> str:
        arrow = "↑" if self.ascending else "↓"
        return f"Sort {self.table.display} by {self.column or '?'} {arrow}"

    async def run(self, ctx):
        table = self.table.get(ctx)
        if table is None:
            raise ValueError(f"table {self.table.display} not found")

        def key(row):
            value = row.get(self.column)
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                return (1, str(value))

        table["rows"].sort(key=key, reverse=not self.ascending)
        self.table.notify(ctx)
