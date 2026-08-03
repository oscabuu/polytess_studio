# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Write a value into a table cell (row by index or key-column match)."""

from __future__ import annotations

from polytess.core import tables
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetAny, PropertyGetNumber,
                                    PropertyGetString, PropertySetTable)


@meta(title="Set Table Cell", category="Tables/Set Table Cell", icon="edit", color="pink",
      description="Writes a value into a table cell; the row is selected by "
                  "index or by matching a key column (e.g. Name=job42)",
      keywords=("update", "state", "cell", "row"))
class SetTableCell(Instruction):

    FIELD_HELP = {
        "table": "Table variable to modify; the node fails if the "
                 "table does not exist.",
        "row_index": "0-based index of the row to change; only used "
                     "when no match column is set.",
        "match_column": "Column used to find the row by value instead "
                        "of by index (e.g. Name); empty = use the row "
                        "index.",
        "match_value": "Value that the match column must equal; the "
                       "node fails when no row matches.",
        "column": "Name of the column whose cell is written.",
        "value": "The value written into the selected cell; can be a "
                 "constant or read from a variable.",
    }

    LEGACY_ALIASES = {"table_name": "table"}

    def __init__(self, table_name: str = "", column: str = "", value=None):
        super().__init__()
        self.table = PropertySetTable(table_name)
        self.row_index = PropertyGetNumber(0)
        self.match_column = ""
        self.match_value = PropertyGetString("")
        self.column = column
        self.value = value if value is not None else PropertyGetAny()

    @property
    def title(self) -> str:
        sel = f"[{self.match_column}={self.match_value}]" if self.match_column \
            else f"[{self.row_index}]"
        return f"Set {self.table.display}{sel}.{self.column or '?'} = {self.value}"

    async def run(self, ctx):
        table = self.table.get(ctx)
        if table is None:
            raise ValueError(f"table {self.table.display} not found")
        if self.match_column:
            index = tables.find_row_index(table, self.match_column,
                                          self.match_value.get(ctx))
            if index < 0:
                raise ValueError(f"no row with {self.match_column}="
                                 f"{self.match_value.get(ctx)!r}")
        else:
            index = int(self.row_index.get(ctx))
        tables.set_cell(table, index, self.column, self.value.get(ctx))
        self.table.notify(ctx)
