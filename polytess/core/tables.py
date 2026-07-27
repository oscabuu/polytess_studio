# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Table data helpers — the ``table`` value type used for CSV configs,
DOE matrices and job-status tables.

A table is a plain JSON-able dict:  {"columns": [str], "rows": [ {col: value} ]}
so it serializes through the normal tagged-JSON machinery without extra code.
"""

from __future__ import annotations

import csv
import os
from typing import Any


def new_table(columns: list[str] | None = None, rows: list[dict] | None = None) -> dict:
    table = {"columns": list(columns) if columns else [], "rows": []}
    for row in rows or []:
        add_row(table, row)
    return table


def coerce_table(value: Any) -> dict:
    if isinstance(value, dict) and "rows" in value:
        table = {"columns": list(value.get("columns", [])),
                 "rows": [dict(r) for r in value.get("rows", [])]}
        for row in table["rows"]:
            for key in row:
                if key not in table["columns"]:
                    table["columns"].append(key)
        return table
    if isinstance(value, list):                 # list of dicts
        return new_table(rows=[dict(r) for r in value if isinstance(r, dict)])
    return new_table()


def columns_of(table: dict) -> list[str]:
    return table.get("columns", [])


def rows_of(table: dict) -> list[dict]:
    return table.get("rows", [])


def row_count(table: dict) -> int:
    return len(rows_of(table))


def add_row(table: dict, row: dict) -> dict:
    row = dict(row)
    for key in row:
        if key not in table["columns"]:
            table["columns"].append(key)
    table["rows"].append(row)
    return row


def cell(table: dict, row_index: int, column: str, default: Any = None) -> Any:
    rows = rows_of(table)
    if -len(rows) <= row_index < len(rows):
        return rows[row_index].get(column, default)
    return default


def set_cell(table: dict, row_index: int, column: str, value: Any) -> None:
    rows = rows_of(table)
    if -len(rows) <= row_index < len(rows):
        rows[row_index][column] = value
        if column not in table["columns"]:
            table["columns"].append(column)


def find_row_index(table: dict, column: str, value: Any) -> int:
    """First row where str(row[column]) == str(value); -1 if none."""
    for index, row in enumerate(rows_of(table)):
        if str(row.get(column)) == str(value):
            return index
    return -1


def convert_scalar(text: str) -> Any:
    """CSV cell -> int / float / bool / str (best effort)."""
    stripped = text.strip()
    if stripped == "":
        return ""
    low = stripped.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        if "." not in stripped and "e" not in low and "," not in stripped:
            return int(stripped)
        return float(stripped)
    except ValueError:
        return stripped


def read_csv(path: str, separator: str = "auto", convert_numbers: bool = True) -> dict:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        if separator == "auto":
            counts = {sep: sample.split("\n")[0].count(sep) for sep in (";", ",", "\t")}
            separator = max(counts, key=counts.get) if any(counts.values()) else ","
        elif separator == "tab":
            separator = "\t"
        reader = csv.reader(fh, delimiter=separator)
        lines = [row for row in reader if any(col.strip() for col in row)]
    if not lines:
        return new_table()
    header = [col.strip() for col in lines[0]]
    table = new_table(columns=header)
    for raw in lines[1:]:
        row = {}
        for index, column in enumerate(header):
            value = raw[index] if index < len(raw) else ""
            row[column] = convert_scalar(value) if convert_numbers else value.strip()
        table["rows"].append(row)
    return table


def write_csv(table: dict, path: str, separator: str = ";") -> None:
    if separator == "tab":
        separator = "\t"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=separator)
        columns = columns_of(table)
        writer.writerow(columns)
        for row in rows_of(table):
            writer.writerow([row.get(col, "") for col in columns])


def summary(table: dict) -> str:
    return f"{row_count(table)} rows × {len(columns_of(table))} cols"


# --------------------------------------------------------------------------- #
# variable-scope access helpers used by table instructions
# --------------------------------------------------------------------------- #

def variables_scope(ctx, scope: str):
    return ctx.graph_variables if scope == "graph" else ctx.globals.variables


def get_table(ctx, scope: str, name: str) -> dict | None:
    variables = variables_scope(ctx, scope)
    if variables is None:
        return None
    value = variables.get(name)
    return value if isinstance(value, dict) and "rows" in value else None


def set_table(ctx, scope: str, name: str, table: dict) -> None:
    variables = variables_scope(ctx, scope)
    if variables is None:
        return
    if variables.exists(name):
        variables.set(name, table)
    else:
        variables.declare(name, "table", table)


def notify_table(ctx, scope: str, name: str) -> None:
    """Emit a change event after in-place mutation (blackboard refresh)."""
    variables = variables_scope(ctx, scope)
    if variables is not None:
        variables._emit(name)
