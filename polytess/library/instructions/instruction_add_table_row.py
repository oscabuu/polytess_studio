# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Append a row to a table variable (creates the table if missing).

The row is given as ``col=value`` pairs separated by ``;`` — values support
{variable} placeholders, so inside a Loop Table you can write e.g.
``Name={Name};File=odir/{Name}/model.spck;ResultFile=odir/{Name}/model.mat``."""

from __future__ import annotations

from polytess.core import tables
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetString, PropertySetTable,
                                    format_with_variables)


@meta(title="Add Table Row", category="Tables/Add Table Row", icon="plus", color="pink",
      description="Appends a row to a table variable; 'col=value;col2=value2' "
                  "with {variable} placeholders (job lists, result tables)",
      keywords=("append", "row", "insert", "jobs"))
class AddTableRow(Instruction):
    LEGACY_ALIASES = {"table_name": "table"}

    FIELD_HELP = {
        "table": "Table variable that receives the new row. The table is "
                 "created automatically if it does not exist yet; the run "
                 "fails if no table variable is selected.",
        "values": "Row content as 'col=value' pairs separated by ';'. "
                  "Values support {variable} placeholders; numbers are "
                  "converted automatically. Pairs without '=' are ignored, "
                  "and with no valid pair the row is skipped with a warning.",
    }

    def __init__(self, table_name: str = "", values: str = ""):
        super().__init__()
        self.table = PropertySetTable(table_name)
        self.values = PropertyGetString(values)

    @property
    def title(self) -> str:
        return f"Add row to {self.table.display}: {self.values}"

    async def run(self, ctx):
        table = self.table.ensure(ctx)
        if table is None:
            raise ValueError(f"table {self.table.display} not available")
        row: dict = {}
        for pair in self.values.get(ctx).split(";"):
            column, sep, raw = pair.partition("=")
            if not sep:
                continue
            rendered = format_with_variables(raw.strip(), ctx)
            row[column.strip()] = tables.convert_scalar(rendered)
        if not row:
            ctx.warning("Add Table Row: no col=value pairs — skipped")
            return
        tables.add_row(table, row)
        self.table.notify(ctx)
