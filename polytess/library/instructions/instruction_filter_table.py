# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Filter table rows into a new table variable (the iloc/subset equivalent)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core import tables
from polytess.core.properties import (PropertyGetString, PropertyGetTable,
                                    PropertySetTable, SetGlobalTable,
                                    SetGraphTable)

_OPS = ["=", "!=", "<", "<=", ">", ">=", "contains", "starts-with", "ends-with"]


def _match(cell_value, op: str, ref: str) -> bool:
    if op in ("<", "<=", ">", ">="):
        try:
            a, b = float(cell_value), float(ref)
        except (TypeError, ValueError):
            return False
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    text = "" if cell_value is None else str(cell_value)
    if op == "=":
        return text == ref or _num_eq(cell_value, ref)
    if op == "!=":
        return not (text == ref or _num_eq(cell_value, ref))
    if op == "contains":
        return ref in text
    if op == "starts-with":
        return text.startswith(ref)
    if op == "ends-with":
        return text.endswith(ref)
    return False


def _num_eq(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


@meta(title="Filter Table", category="Tables/Filter Table", icon="filter", color="pink",
      description="Copies matching rows into a new table variable; row range "
                  "filtering via the special column '#' (row index)",
      keywords=("subset", "select", "where", "rows"))
class FilterTable(Instruction):
    FIELD_CHOICES = {"operation": _OPS}
    LEGACY_ALIASES = {"table_name": "table"}

    FIELD_HELP = {
        "table": "Table variable whose rows are filtered; the step fails if "
                 "the table does not exist.",
        "column": "Column the comparison reads; the special column '#' "
                  "compares against the row index (0-based) for row-range "
                  "filtering.",
        "operation": "Comparison operator: '=' / '!=' match text or number "
                     "equality, '<' '<=' '>' '>=' compare numerically "
                     "(non-numbers never match), 'contains' / 'starts-with' "
                     "/ 'ends-with' test the cell text.",
        "value": "Reference value to compare each cell against (supports "
                 "variable sources); numbers are compared numerically where "
                 "the operator requires it.",
        "target_table": "Table variable that receives the matching rows; "
                        "the result is written into the chosen graph/global "
                        "table. Left empty, the source table variable is "
                        "overwritten in place.",
    }

    def __init__(self, table_name: str = "", column: str = "", operation: str = "=",
                 value: str = "", target_table: str = ""):
        super().__init__()
        self.table = PropertyGetTable(table_name)
        self.column = column                # "#" filters on the row index
        self.operation = operation
        self.value = PropertyGetString(value)
        self.target_table = PropertySetTable(target_table)

    @property
    def title(self) -> str:
        return f"Filter {self.table.display} where {self.column or '?'} " \
               f"{self.operation} {self.value} -> {self.target_table.display}"

    async def run(self, ctx):
        table = self.table.get(ctx)
        if table is None:
            raise ValueError(f"table {self.table.display} not found")
        ref = self.value.get(ctx)
        out = tables.new_table(columns=tables.columns_of(table))
        for index, row in enumerate(tables.rows_of(table)):
            probe = index if self.column == "#" else row.get(self.column)
            if _match(probe, self.operation, ref):
                out["rows"].append(dict(row))
        target = self.target_table.source
        if not getattr(target, "name", ""):
            # no target set: overwrite the source table variable
            name = getattr(self.table.source, "name", "")
            if not name:
                raise ValueError("Filter Table: no target table set")
            scope_id = getattr(self.table.source, "scope_id", "graph")
            target = (SetGlobalTable if scope_id == "global" else SetGraphTable)(name)
        target.set(out, ctx)
        ctx.info(f"Filter Table: {tables.row_count(out)}/{tables.row_count(table)} "
                 f"rows -> {target.display}")
