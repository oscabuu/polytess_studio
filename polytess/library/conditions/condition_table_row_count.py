# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Condition: compare the row count of a table variable
(consistency checks, 'still pending jobs?')."""

from __future__ import annotations

from polytess.core import tables
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetNumber, PropertyGetTable

_OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


@meta(title="Table Row Count", category="Tables/Table Row Count", icon="list",
      color="pink", description="Compares the number of rows in a table variable")
class TableRowCount(Condition):
    FIELD_CHOICES = {"comparison": list(_OPS)}
    LEGACY_ALIASES = {"table_name": "table"}

    def __init__(self, table_name: str = "", comparison: str = "=", count: float = 0.0):
        super().__init__()
        self.table = PropertyGetTable(table_name)
        self.comparison = comparison
        self.count = PropertyGetNumber(count)

    @property
    def summary(self) -> str:
        return f"rows({self.table.display}) {self.comparison} {self.count}"

    def run(self, ctx):
        table = self.table.get(ctx)
        rows = float(tables.row_count(table)) if table is not None else 0.0
        return _OPS.get(self.comparison, _OPS["="])(rows, self.count.get(ctx))
