# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Loop over the rows of a table variable."""

from __future__ import annotations

from polytess.core import tables
from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetTable


@meta(title="Loop Table", category="Tables/Loop Table", icon="repeat", color="pink",
      description="Runs the nested actions once per table row. The row dict is "
                  "the Loop Target; with 'expose columns' every column value is "
                  "additionally written into a graph variable of the same name "
                  "(usable as {column} in templates)",
      keywords=("for", "rows", "iterate", "doe", "config"))
class LoopTable(Instruction):
    LEGACY_ALIASES = {"table_name": "table"}

    FIELD_HELP = {
        "table": "Table variable to iterate; the nested actions run once "
                 "per row. A missing table only logs a warning and skips "
                 "the loop.",
        "expose_columns": "If enabled (default), every column value of the "
                          "current row is written into a graph variable of "
                          "the same name, usable as {column} in templates.",
        "row_index_to": "Name of the graph variable that receives the "
                        "current row index (0-based, default 'row_index'); "
                        "empty = no index variable is written. Only used "
                        "when 'expose columns' is enabled.",
        "actions": "Instructions executed for each row; inside them the row "
                   "dict is available as 'Loop Target' / {target}.",
    }

    def __init__(self, table_name: str = ""):
        super().__init__()
        self.table = PropertyGetTable(table_name)
        self.expose_columns = True
        self.row_index_to = "row_index"      # graph variable receiving the index
        self.actions = InstructionList()

    @property
    def title(self) -> str:
        return f"Loop table {self.table.display} " \
               f"({len(self.actions)} actions)"

    async def run(self, ctx):
        table = self.table.get(ctx)
        if table is None:
            ctx.warning(f"Loop Table: table {self.table.display} not found")
            return
        scope = ctx.graph_variables
        for index, row in enumerate(list(tables.rows_of(table))):
            if ctx.is_cancelled or (self._parent is not None and self._parent.is_cancelled):
                return
            if self.expose_columns and scope is not None:
                if self.row_index_to:
                    scope.set(self.row_index_to, index)
                for column, value in row.items():
                    scope.set(column, value)
            await self.actions.run(ctx.child(target=row))
