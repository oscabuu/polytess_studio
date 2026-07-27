# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Write a table variable to a CSV file."""

from __future__ import annotations

import asyncio

from polytess.core import tables
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath, PropertyGetTable


@meta(title="Write Table To CSV", category="Tables/Write Table To CSV", icon="save",
      color="pink", description="Writes a table variable to a CSV file",
      keywords=("csv", "export", "save"))
class WriteTableToCsv(Instruction):
    FIELD_CHOICES = {"separator": [";", ",", "tab"]}
    LEGACY_ALIASES = {"table_name": "table"}

    def __init__(self, table_name: str = "", path: str = "", separator: str = ";"):
        super().__init__()
        self.table = PropertyGetTable(table_name)
        self.path = PropertyGetPath(path)
        self.separator = separator

    @property
    def title(self) -> str:
        return f"Write {self.table.display} -> {self.path}"

    async def run(self, ctx):
        table = self.table.get(ctx)
        if table is None:
            raise ValueError(f"table {self.table.display} not found")
        path = ctx.resolve_path(self.path.get(ctx))
        await asyncio.to_thread(tables.write_csv, table, path, self.separator)
        ctx.info(f"Wrote table {self.table.display} ({tables.summary(table)}) -> {path}")
