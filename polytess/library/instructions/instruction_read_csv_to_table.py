# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Read a CSV file into a table variable."""

from __future__ import annotations

import asyncio

from polytess.core import tables
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath, PropertySetTable


@meta(title="Read CSV To Table", category="Tables/Read CSV To Table", icon="list",
      color="pink",
      description="Reads a CSV file (auto-detected or fixed separator) into a "
                  "table variable; numbers and booleans are converted",
      keywords=("csv", "import", "config", "doe", "matrix"))
class ReadCsvToTable(Instruction):
    FIELD_CHOICES = {"separator": ["auto", ";", ",", "tab"]}

    FIELD_HELP = {
        "path": "CSV file to read; relative paths resolve against the "
                "working directory.",
        "separator": "Column separator: 'auto' detects it from the file "
                     "content, or force ';', ',' or a tab character.",
        "convert_numbers": "When enabled (default), cell texts that look "
                           "like numbers or booleans are converted to "
                           "their typed values instead of staying strings.",
        "table": "Table variable that receives the parsed rows; an "
                 "existing table of the same name is replaced.",
    }

    LEGACY_ALIASES = {"table_name": "table"}

    def __init__(self, path: str = "", table_name: str = "", separator: str = "auto"):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.separator = separator
        self.convert_numbers = True
        self.table = PropertySetTable(table_name)

    @property
    def title(self) -> str:
        return f"Read CSV {self.path} -> {self.table.display}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        table = await asyncio.to_thread(tables.read_csv, path, self.separator,
                                        self.convert_numbers)
        self.table.set(table, ctx)
        ctx.info(f"Read CSV {path}: {tables.summary(table)}")
