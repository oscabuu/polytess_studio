# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Property system — the pivot of flexibility.

A field of an Instruction/Condition is not a raw value but a
``PropertyGet[T]`` / ``PropertySet[T]`` wrapper holding an exchangeable
polymorphic *source*. The simplest
source is a constant; others read/write graph or global variables, pick
list elements, format strings from variables, read env vars, etc.

Compatibility for the selector menu is declared through ``value_type``
("string" | "number" | "bool" | "path" | "list" | "any").
"""

from __future__ import annotations

import datetime as _dt
import os
import random
from typing import Any

from polytess.core.context import Context
from polytess.core.metadata import meta, iter_subclasses
from polytess.core.polymorphic import PolymorphicItem
from polytess.core.values import ValueBool, ValueNumber


# --------------------------------------------------------------------------- #
# Source bases
# --------------------------------------------------------------------------- #

class PropertySource(PolymorphicItem):
    """TPropertyTypeGet — produces a value."""

    value_type: str = "any"

    def get(self, ctx: Context) -> Any:
        return None

    @property
    def display(self) -> str:
        """Short text used inside dynamic instruction titles."""
        return self.title


class SetSource(PolymorphicItem):
    """TPropertyTypeSet — consumes a value (and can read it back)."""

    value_type: str = "any"

    def set(self, value: Any, ctx: Context) -> None:
        pass

    def get(self, ctx: Context) -> Any:
        return None

    @property
    def display(self) -> str:
        return self.title


# --------------------------------------------------------------------------- #
# Get sources: constants
# --------------------------------------------------------------------------- #

@meta(title="String", category="Constants/String", icon="string", color="yellow",
      description="A constant string of characters", keywords=("value", "text"))
class GetConstantString(PropertySource):
    value_type = "string"

    FIELD_HELP = {
        "value": "The constant text used as-is.",
    }

    def __init__(self, value: str = ""):
        super().__init__()
        self.value = value

    def get(self, ctx):
        return self.value

    @property
    def display(self):
        return repr(self.value) if self.value != "" else "''"


@meta(title="Number", category="Constants/Number", icon="number", color="green",
      description="A constant number", keywords=("value", "float", "integer"))
class GetConstantNumber(PropertySource):
    value_type = "number"

    FIELD_HELP = {
        "value": "The constant numeric value (stored as float).",
    }

    def __init__(self, value: float = 0.0):
        super().__init__()
        self.value = float(value)

    def get(self, ctx):
        return self.value

    @property
    def display(self):
        return f"{self.value:g}"


@meta(title="Boolean", category="Constants/Boolean", icon="toggle", color="red",
      description="A constant true/false value", keywords=("value", "flag"))
class GetConstantBool(PropertySource):
    value_type = "bool"

    FIELD_HELP = {
        "value": "The constant true/false value.",
    }

    def __init__(self, value: bool = True):
        super().__init__()
        self.value = bool(value)

    def get(self, ctx):
        return self.value

    @property
    def display(self):
        return "True" if self.value else "False"


@meta(title="Path", category="Constants/Path", icon="folder", color="blue",
      description="A constant file or directory path (supports ~ and $VARS)",
      keywords=("file", "folder", "directory"))
class GetConstantPath(PropertySource):
    value_type = "path"

    FIELD_HELP = {
        "value": "The file or directory path. ~ and $VARS are expanded; a "
                 "relative path resolves against the working directory.",
    }

    def __init__(self, value: str = ""):
        super().__init__()
        self.value = value

    def get(self, ctx):
        return ctx.resolve_path(self.value) if self.value else ""

    @property
    def display(self):
        return self.value or "(none)"


@meta(title="Date", category="Constants/Date", icon="clock", color="teal",
      description="A fixed date/time — 'YYYY-MM-DD HH:MM:SS' (ISO-8601 and "
                  "DD.MM.YYYY also accepted)",
      keywords=("time", "datetime", "when"))
class GetConstantDate(PropertySource):
    value_type = "date"

    FIELD_HELP = {
        "value": "The fixed date/time as text — 'YYYY-MM-DD HH:MM:SS' "
                 "(ISO-8601 and DD.MM.YYYY are also accepted).",
    }

    def __init__(self, value: str = ""):
        super().__init__()
        self.value = value

    def get(self, ctx):
        return self.value

    @property
    def display(self):
        return self.value or "(no date)"


@meta(title="Vector3", category="Constants/Vector3", icon="axes", color="green",
      description="A fixed (x, y, z) vector", keywords=("position", "xyz"))
class GetConstantVector3(PropertySource):
    value_type = "vector3"

    FIELD_HELP = {
        "x": "The X component of the vector.",
        "y": "The Y component of the vector.",
        "z": "The Z component of the vector.",
    }

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        super().__init__()
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def get(self, ctx):
        return [self.x, self.y, self.z]

    @property
    def display(self):
        return f"({self.x:g}, {self.y:g}, {self.z:g})"


@meta(title="Transform", category="Constants/Transform", icon="transform",
      color="teal", description="A fixed position + rotation",
      keywords=("pose", "placement"))
class GetConstantTransform(PropertySource):
    value_type = "transform"

    FIELD_HELP = {
        "pos_x": "The X component of the position.",
        "pos_y": "The Y component of the position.",
        "pos_z": "The Z component of the position.",
        "rot_x": "The rotation around the X axis.",
        "rot_y": "The rotation around the Y axis.",
        "rot_z": "The rotation around the Z axis.",
    }

    def __init__(self):
        super().__init__()
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0

    def get(self, ctx):
        return {"pos": [self.pos_x, self.pos_y, self.pos_z],
                "rot": [self.rot_x, self.rot_y, self.rot_z]}

    @property
    def display(self):
        return (f"pos ({self.pos_x:g}, {self.pos_y:g}, {self.pos_z:g}) · "
                f"rot ({self.rot_x:g}, {self.rot_y:g}, {self.rot_z:g})")


@meta(title="None", category="Constants/None", icon="null", color="text-light",
      description="No value")
class GetNone(PropertySource):
    value_type = "any"

    def get(self, ctx):
        return None

    @property
    def display(self):
        return "(none)"


# --------------------------------------------------------------------------- #
# Get sources: variables
# --------------------------------------------------------------------------- #

@meta(title="Graph Variable", category="Variables/Graph Variable", icon="variable",
      color="purple", description="Read a variable defined on the current graph",
      keywords=("local", "blackboard"))
class GetGraphVariable(PropertySource):
    value_type = "any"
    ref_kind = "variable"

    FIELD_HELP = {
        "name": "Name of the graph variable to read; None if it does "
                "not exist.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        scope = ctx.graph_variables
        return scope.get(self.name) if scope is not None else None

    @property
    def display(self):
        return f"graph:{self.name or '?'}"


@meta(title="Global Variable", category="Variables/Global Variable", icon="globe",
      color="purple", description="Read an application-wide global variable")
class GetGlobalVariable(PropertySource):
    value_type = "any"
    ref_kind = "variable"

    FIELD_HELP = {
        "name": "Name of the application-wide global variable to read; "
                "None if it does not exist.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        return ctx.globals.variables.get(self.name)

    @property
    def display(self):
        return f"global:{self.name or '?'}"


@meta(title="Loop Target", category="Variables/Loop Target", icon="target", color="teal",
      description="The current element while iterating a list (Loop List)")
class GetTarget(PropertySource):
    value_type = "any"

    def get(self, ctx):
        return ctx.target

    @property
    def display(self):
        return "target"


@meta(title="List", category="Constants/List", icon="list", color="purple",
      description="A list of values entered directly (numbers and booleans "
                  "are converted)", keywords=("value", "items", "direct"))
class GetConstantList(PropertySource):
    value_type = "list"

    FIELD_HELP = {
        "items": "The list entries. Text entries that look like numbers "
                 "or true/false are converted to those types.",
    }

    def __init__(self, items: list | None = None):
        super().__init__()
        self.items = list(items) if items else []

    def get(self, ctx):
        from polytess.core import tables
        return [tables.convert_scalar(v) if isinstance(v, str) else v
                for v in self.items]

    @property
    def display(self):
        return f"[{len(self.items)} items]"


@meta(title="Graph List Variable", category="Variables/Graph List Variable",
      icon="list", color="purple",
      description="Read a list variable of the current graph",
      keywords=("local", "blackboard"))
class GetGraphList(PropertySource):
    value_type = "list"
    ref_kind = "list"

    FIELD_HELP = {
        "name": "Name of the graph list variable to read; yields a copy "
                "of its items, or None if it does not exist.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        lists = ctx.graph_lists
        lst = lists.get(self.name) if lists is not None else None
        return list(lst.items) if lst is not None else None

    @property
    def display(self):
        return f"graph:{self.name or '?'}"


@meta(title="Global List Variable", category="Variables/Global List Variable",
      icon="globe", color="purple",
      description="Read an application-wide global list variable")
class GetGlobalList(PropertySource):
    value_type = "list"
    ref_kind = "list"

    FIELD_HELP = {
        "name": "Name of the global list variable to read; yields a copy "
                "of its items, or None if it does not exist.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        lst = ctx.globals.lists.get(self.name)
        return list(lst.items) if lst is not None else None

    @property
    def display(self):
        return f"global:{self.name or '?'}"


@meta(title="Split String", category="Computed/Split String", icon="list",
      color="purple",
      description="Splits a formatted string into a list — {name} placeholders "
                  "are replaced by variables first (e.g. a node-list column "
                  "'1001; 1002' from a Loop Table row)",
      keywords=("list", "parse", "separator", "template", "nodes"))
class GetSplitString(PropertySource):
    value_type = "list"

    FIELD_HELP = {
        "template": "The text to split. {name} placeholders are replaced "
                    "by graph/global variables first, {target} by the loop "
                    "target and {workdir} by the working directory.",
        "separator": "The delimiter to split at (default ','). With ',' "
                     "semicolons are treated as commas too; parts are "
                     "trimmed and empty parts dropped.",
    }

    def __init__(self, template: str = "", separator: str = ","):
        super().__init__()
        self.template = template
        self.separator = separator

    def get(self, ctx):
        text = format_with_variables(self.template, ctx)
        separator = self.separator or ","
        if separator == ",":
            text = text.replace(";", ",")     # tolerate CSV-style node lists
        return [part.strip() for part in text.split(separator) if part.strip()]

    @property
    def display(self):
        return f"split({self.template!r})"


@meta(title="Graph Table Variable", category="Variables/Graph Table Variable",
      icon="list", color="pink",
      description="Read a table variable of the current graph")
class GetGraphTable(PropertySource):
    value_type = "table"
    ref_kind = "table"
    scope_id = "graph"

    FIELD_HELP = {
        "name": "Name of the table variable to read (graph or global, "
                "depending on the source); None if it does not exist.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        from polytess.core import tables
        return tables.get_table(ctx, self.scope_id, self.name)

    @property
    def display(self):
        return f"{self.scope_id}:{self.name or '?'}"


@meta(title="Global Table Variable", category="Variables/Global Table Variable",
      icon="globe", color="pink",
      description="Read an application-wide global table variable")
class GetGlobalTable(GetGraphTable):
    scope_id = "global"


@meta(title="List Element", category="Variables/List Element", icon="list", color="purple",
      description="Pick an element from a list variable",
      parameters=(("List", "Name of the list variable"),
                  ("Pick", "first / last / index / random"),
                  ("Index", "Element index when Pick is 'index'")))
class GetListElement(PropertySource):
    value_type = "any"
    FIELD_CHOICES = {"scope": ["graph", "global"], "pick": ["first", "last", "index", "random"]}

    FIELD_HELP = {
        "scope": "Where the list lives: 'graph' (current graph) or "
                 "'global' (application-wide).",
        "list_name": "Name of the list variable to pick from; None if it "
                     "is missing or empty.",
        "pick": "Which element to return: 'first', 'last', 'random', or "
                "'index' to use the Index field.",
        "index": "0-based element index, used only when Pick is 'index'.",
    }

    def __init__(self, list_name: str = "", pick: str = "first", index: int = 0,
                 scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.list_name = list_name
        self.pick = pick
        self.index = index

    def _list(self, ctx):
        lists = ctx.graph_lists if self.scope == "graph" else ctx.globals.lists
        return lists.get(self.list_name) if lists is not None else None

    def get(self, ctx):
        lst = self._list(ctx)
        if lst is None or len(lst) == 0:
            return None
        if self.pick == "first":
            return lst.get(0)
        if self.pick == "last":
            return lst.get(len(lst) - 1)
        if self.pick == "random":
            return random.choice(lst.items)
        return lst.get(int(self.index))

    @property
    def display(self):
        sel = f"[{int(self.index)}]" if self.pick == "index" else f".{self.pick}"
        return f"{self.scope}:{self.list_name or '?'}{sel}"


@meta(title="List Count", category="Variables/List Count", icon="number", color="green",
      description="The number of elements in a list variable")
class GetListCount(PropertySource):
    value_type = "number"
    FIELD_CHOICES = {"scope": ["graph", "global"]}

    FIELD_HELP = {
        "scope": "Where the list lives: 'graph' (current graph) or "
                 "'global' (application-wide).",
        "list_name": "Name of the list variable to count; 0 if it does "
                     "not exist.",
    }

    def __init__(self, list_name: str = "", scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.list_name = list_name

    def get(self, ctx):
        lists = ctx.graph_lists if self.scope == "graph" else ctx.globals.lists
        lst = lists.get(self.list_name) if lists is not None else None
        return float(len(lst)) if lst is not None else 0.0

    @property
    def display(self):
        return f"len({self.scope}:{self.list_name or '?'})"


# --------------------------------------------------------------------------- #
# Get sources: computed
# --------------------------------------------------------------------------- #

@meta(title="Formatted String", category="Computed/Formatted String", icon="string",
      color="yellow",
      description="A template where {name} is replaced by graph/global variables "
                  "and {target} by the loop target — ideal for input files and paths",
      keywords=("template", "format", "interpolate"))
class GetStringFormat(PropertySource):
    value_type = "string"

    FIELD_HELP = {
        "template": "The text template. {name} placeholders are replaced "
                    "by graph/global variables, {target} by the loop "
                    "target and {workdir} by the working directory.",
    }

    def __init__(self, template: str = ""):
        super().__init__()
        self.template = template

    def get(self, ctx):
        return format_with_variables(self.template, ctx)

    @property
    def display(self):
        return f"f{self.template!r}"


@meta(title="Formatted Path", category="Computed/Formatted Path", icon="folder",
      color="blue",
      description="A path template where {name} is replaced by variables; "
                  "relative paths resolve against the working directory")
class GetPathFormat(PropertySource):
    value_type = "path"

    FIELD_HELP = {
        "template": "The path template. {name} placeholders are replaced "
                    "by graph/global variables, {target} by the loop "
                    "target and {workdir} by the working directory; a "
                    "relative result resolves against the working "
                    "directory.",
    }

    def __init__(self, template: str = ""):
        super().__init__()
        self.template = template

    def get(self, ctx):
        text = format_with_variables(self.template, ctx)
        return ctx.resolve_path(text) if text else ""

    @property
    def display(self):
        return f"f{self.template!r}"


@meta(title="Date / Time", category="Computed/Date Time", icon="clock", color="teal",
      description="The current date/time formatted with strftime")
class GetDateTime(PropertySource):
    value_type = "string"

    FIELD_HELP = {
        "format": "strftime pattern applied to the current date/time, "
                  "e.g. %Y-%m-%d_%H-%M-%S.",
    }

    def __init__(self, format: str = "%Y-%m-%d_%H-%M-%S"):
        super().__init__()
        self.format = format

    def get(self, ctx):
        return _dt.datetime.now().strftime(self.format)

    @property
    def display(self):
        return "now()"


@meta(title="Environment Variable", category="Computed/Environment Variable",
      icon="globe", color="teal", description="Read an OS environment variable")
class GetEnvironmentVariable(PropertySource):
    value_type = "string"

    FIELD_HELP = {
        "name": "Name of the OS environment variable to read.",
        "default": "Fallback text returned when the environment variable "
                   "is not set.",
    }

    def __init__(self, name: str = "", default: str = ""):
        super().__init__()
        self.name = name
        self.default = default

    def get(self, ctx):
        return os.environ.get(self.name, self.default)

    @property
    def display(self):
        return f"${self.name or '?'}"


@meta(title="Random Number", category="Computed/Random Number", icon="number",
      color="green", description="A uniform random number in [min, max]")
class GetRandomNumber(PropertySource):
    value_type = "number"

    FIELD_HELP = {
        "minimum": "Lower bound of the uniform random range (inclusive).",
        "maximum": "Upper bound of the uniform random range (inclusive).",
    }

    def __init__(self, minimum: float = 0.0, maximum: float = 1.0):
        super().__init__()
        self.minimum = float(minimum)
        self.maximum = float(maximum)

    def get(self, ctx):
        return random.uniform(self.minimum, self.maximum)

    @property
    def display(self):
        return f"rnd({self.minimum:g},{self.maximum:g})"


@meta(title="Working Directory", category="Computed/Working Directory", icon="folder",
      color="blue", description="The workflow working directory")
class GetWorkdir(PropertySource):
    value_type = "path"

    def get(self, ctx):
        return ctx.workdir

    @property
    def display(self):
        return "workdir"


@meta(title="Table Cell", category="Variables/Table Cell", icon="list", color="pink",
      description="Read a cell from a table variable (row by index or by "
                  "matching a key column)")
class GetTableCell(PropertySource):
    value_type = "any"
    FIELD_CHOICES = {"scope": ["graph", "global"]}

    FIELD_HELP = {
        "scope": "Where the table lives: 'graph' (current graph) or "
                 "'global' (application-wide).",
        "table_name": "Name of the table variable to read from.",
        "row_index": "0-based row index; ignored when Match Column is "
                     "set.",
        "match_column": "Optional: column searched for Match Value; the "
                        "first matching row is used instead of Row Index.",
        "match_value": "Value compared (as text) against Match Column to "
                       "find the row.",
        "column": "Name of the column whose cell value is returned.",
    }

    def __init__(self, table_name: str = "", row_index: int = 0, column: str = "",
                 match_column: str = "", match_value: str = "", scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.table_name = table_name
        self.row_index = row_index
        self.match_column = match_column     # optional: overrides row_index
        self.match_value = match_value
        self.column = column

    def get(self, ctx):
        from polytess.core import tables
        table = tables.get_table(ctx, self.scope, self.table_name)
        if table is None:
            return None
        index = self.row_index
        if self.match_column:
            index = tables.find_row_index(table, self.match_column, self.match_value)
            if index < 0:
                return None
        return tables.cell(table, int(index), self.column)

    @property
    def display(self):
        sel = f"[{self.match_column}={self.match_value}]" if self.match_column \
            else f"[{int(self.row_index)}]"
        return f"{self.table_name or '?'}{sel}.{self.column or '?'}"


@meta(title="Table Row Count", category="Variables/Table Row Count", icon="number",
      color="pink", description="The number of rows in a table variable")
class GetTableRowCount(PropertySource):
    value_type = "number"
    FIELD_CHOICES = {"scope": ["graph", "global"]}

    FIELD_HELP = {
        "scope": "Where the table lives: 'graph' (current graph) or "
                 "'global' (application-wide).",
        "table_name": "Name of the table variable whose rows are "
                      "counted; 0 if it does not exist.",
    }

    def __init__(self, table_name: str = "", scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.table_name = table_name

    def get(self, ctx):
        from polytess.core import tables
        table = tables.get_table(ctx, self.scope, self.table_name)
        return float(tables.row_count(table)) if table is not None else 0.0

    @property
    def display(self):
        return f"rows({self.table_name or '?'})"


def format_with_variables(template: str, ctx: Context) -> str:
    """Replace {name} with graph/global variable values, {target} with ctx.target."""

    def _pretty(value):
        # integral floats render without the trailing ".0" (nicer in paths)
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    class _Lookup(dict):
        def __missing__(self, key):
            if key == "target":
                return _pretty(ctx.target)
            if key == "workdir":
                return ctx.workdir
            scope = ctx.graph_variables
            if scope is not None and scope.exists(key):
                return _pretty(scope.get(key))
            if ctx.globals.variables.exists(key):
                return _pretty(ctx.globals.variables.get(key))
            return "{" + key + "}"

    try:
        return template.format_map(_Lookup())
    except (ValueError, IndexError):
        return template


# --------------------------------------------------------------------------- #
# Set sources
# --------------------------------------------------------------------------- #

@meta(title="None", category="Targets/None", icon="null", color="text-light",
      description="Discard the value")
class SetNone(SetSource):
    value_type = "any"

    @property
    def display(self):
        return "(none)"


@meta(title="Graph Variable", category="Variables/Graph Variable", icon="variable",
      color="purple", description="Write into a variable of the current graph")
class SetGraphVariable(SetSource):
    value_type = "any"
    ref_kind = "variable"

    FIELD_HELP = {
        "name": "Name of the graph variable to write the value into.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def set(self, value, ctx):
        scope = ctx.graph_variables
        if scope is not None:
            scope.set(self.name, value)

    def get(self, ctx):
        scope = ctx.graph_variables
        return scope.get(self.name) if scope is not None else None

    @property
    def display(self):
        return f"graph:{self.name or '?'}"


@meta(title="Global Variable", category="Variables/Global Variable", icon="globe",
      color="purple", description="Write into an application-wide global variable")
class SetGlobalVariable(SetSource):
    value_type = "any"
    ref_kind = "variable"

    FIELD_HELP = {
        "name": "Name of the application-wide global variable to write "
                "the value into.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def set(self, value, ctx):
        ctx.globals.variables.set(self.name, value)

    def get(self, ctx):
        return ctx.globals.variables.get(self.name)

    @property
    def display(self):
        return f"global:{self.name or '?'}"


@meta(title="List Element", category="Variables/List Element", icon="list", color="purple",
      description="Write into a list variable (set index / push / insert first)")
class SetListElement(SetSource):
    value_type = "any"
    FIELD_CHOICES = {"scope": ["graph", "global"],
                     "mode": ["push", "insert-first", "index"]}

    FIELD_HELP = {
        "scope": "Where the list lives: 'graph' (current graph) or "
                 "'global' (application-wide).",
        "list_name": "Name of the list variable to write into (created "
                     "if missing).",
        "mode": "How to store the value: 'push' appends, 'insert-first' "
                "prepends, 'index' overwrites at Index.",
        "index": "0-based element index for mode 'index'; out-of-range "
                 "indices append instead.",
    }

    def __init__(self, list_name: str = "", mode: str = "push", index: int = 0,
                 scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.list_name = list_name
        self.mode = mode
        self.index = index

    def _lists(self, ctx):
        return ctx.graph_lists if self.scope == "graph" else ctx.globals.lists

    def set(self, value, ctx):
        lists = self._lists(ctx)
        if lists is None:
            return
        lst = lists.require(self.list_name)
        if self.mode == "push":
            lst.push(value)
        elif self.mode == "insert-first":
            lst.insert(0, value)
        else:
            idx = int(self.index)
            if 0 <= idx < len(lst):
                lst.set(idx, value)
            else:
                lst.push(value)
        lists.notify(self.list_name)

    def get(self, ctx):
        lists = self._lists(ctx)
        lst = lists.get(self.list_name) if lists is not None else None
        if lst is None or len(lst) == 0:
            return None
        return lst.get(int(self.index) if self.mode == "index" else -1)

    @property
    def display(self):
        return f"{self.scope}:{self.list_name or '?'}.{self.mode}"


@meta(title="Graph List Variable", category="Variables/Graph List Variable",
      icon="list", color="purple",
      description="A list variable of the current graph (created if missing)")
class SetGraphList(SetSource):
    value_type = "list"
    ref_kind = "list"

    FIELD_HELP = {
        "name": "Name of the list variable to write (graph or global, "
                "depending on the source); created if missing, replaced "
                "by the assigned items.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def _lists(self, ctx):
        return ctx.graph_lists

    def variable(self, ctx):
        lists = self._lists(ctx)
        return lists.get(self.name) if lists is not None else None

    def require(self, ctx, type_id: str = "string"):
        lists = self._lists(ctx)
        return lists.require(self.name, type_id) if lists is not None else None

    def notify(self, ctx) -> None:
        lists = self._lists(ctx)
        if lists is not None:
            lists.notify(self.name)

    def set(self, value, ctx):
        lst = self.require(ctx)
        if lst is None:
            return
        lst.clear()
        for item in value or []:
            lst.push(item)
        self.notify(ctx)

    def get(self, ctx):
        lst = self.variable(ctx)
        return list(lst.items) if lst is not None else None

    def push(self, value, ctx) -> None:
        lst = self.require(ctx)
        if lst is not None:
            lst.push(value)
            self.notify(ctx)

    def clear(self, ctx) -> None:
        lst = self.variable(ctx)
        if lst is not None:
            lst.clear()
            self.notify(ctx)

    @property
    def display(self):
        return f"graph:{self.name or '?'}"


@meta(title="Global List Variable", category="Variables/Global List Variable",
      icon="globe", color="purple",
      description="An application-wide global list variable (created if missing)")
class SetGlobalList(SetGraphList):

    def _lists(self, ctx):
        return ctx.globals.lists

    @property
    def display(self):
        return f"global:{self.name or '?'}"


@meta(title="Graph Table Variable", category="Variables/Graph Table Variable",
      icon="list", color="pink",
      description="A table variable of the current graph (created if missing)")
class SetGraphTable(SetSource):
    value_type = "table"
    ref_kind = "table"
    scope_id = "graph"

    FIELD_HELP = {
        "name": "Name of the table variable to write (graph or global, "
                "depending on the source); created if missing.",
    }

    def __init__(self, name: str = ""):
        super().__init__()
        self.name = name

    def get(self, ctx):
        from polytess.core import tables
        return tables.get_table(ctx, self.scope_id, self.name)

    def set(self, value, ctx):
        from polytess.core import tables
        tables.set_table(ctx, self.scope_id, self.name, value)

    def notify(self, ctx) -> None:
        from polytess.core import tables
        tables.notify_table(ctx, self.scope_id, self.name)

    def ensure(self, ctx):
        """The live table dict, creating an empty table variable if missing."""
        from polytess.core import tables
        table = self.get(ctx)
        if table is None:
            self.set(tables.new_table(), ctx)
            table = self.get(ctx)
        return table

    @property
    def display(self):
        return f"{self.scope_id}:{self.name or '?'}"


@meta(title="Global Table Variable", category="Variables/Global Table Variable",
      icon="globe", color="pink",
      description="An application-wide global table variable (created if missing)")
class SetGlobalTable(SetGraphTable):
    scope_id = "global"


# --------------------------------------------------------------------------- #
# Property wrappers (the fields living inside instructions/conditions)
# --------------------------------------------------------------------------- #

class PropertyGet(PolymorphicItem):
    """TPropertyGet — wraps an exchangeable get-source."""

    value_type: str = "any"

    def __init__(self, source: PropertySource | None = None):
        super().__init__()
        self.source: PropertySource = source if source is not None else self._default_source()

    @classmethod
    def _default_source(cls) -> PropertySource:
        return GetNone()

    def get(self, ctx: Context) -> Any:
        return self.source.get(ctx) if self.source is not None else None

    @property
    def display(self) -> str:
        return self.source.display if self.source is not None else "(none)"

    def __str__(self) -> str:
        return self.display

    @classmethod
    def compatible_sources(cls) -> list[type]:
        out = []
        for src in iter_subclasses(PropertySource):
            # container types match exactly — a list/table slot only accepts
            # list/table sources, not "any" scalars
            if cls.value_type in ("list", "table"):
                if src.value_type == cls.value_type:
                    out.append(src)
            elif cls.value_type == "any" or src.value_type in ("any", cls.value_type):
                out.append(src)
        return out


@meta(hidden=True)
class PropertyGetString(PropertyGet):
    value_type = "string"

    def __init__(self, value: str | PropertySource | None = None):
        source = GetConstantString(value) if isinstance(value, str) else value
        super().__init__(source)

    @classmethod
    def _default_source(cls):
        return GetConstantString()

    def get(self, ctx):
        value = super().get(ctx)
        return "" if value is None else str(value)


@meta(hidden=True)
class PropertyGetNumber(PropertyGet):
    value_type = "number"

    def __init__(self, value: float | int | PropertySource | None = None):
        source = GetConstantNumber(value) if isinstance(value, (int, float)) else value
        super().__init__(source)

    @classmethod
    def _default_source(cls):
        return GetConstantNumber()

    def get(self, ctx):
        value = super().get(ctx)
        try:
            return ValueNumber.coerce(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0


@meta(hidden=True)
class PropertyGetBool(PropertyGet):
    value_type = "bool"

    def __init__(self, value: bool | PropertySource | None = None):
        source = GetConstantBool(value) if isinstance(value, bool) else value
        super().__init__(source)

    @classmethod
    def _default_source(cls):
        return GetConstantBool()

    def get(self, ctx):
        return ValueBool.coerce(super().get(ctx))


@meta(hidden=True)
class PropertyGetPath(PropertyGet):
    value_type = "path"

    def __init__(self, value: str | PropertySource | None = None):
        source = GetConstantPath(value) if isinstance(value, str) else value
        super().__init__(source)

    @classmethod
    def _default_source(cls):
        return GetConstantPath()

    def get(self, ctx):
        value = super().get(ctx)
        return "" if value is None else str(value)


@meta(hidden=True)
class PropertyGetDate(PropertyGet):
    """A date slot: fixed date or variable. ``get`` returns the raw value —
    parse with :func:`polytess.core.dates.parse_date`."""

    value_type = "date"

    def __init__(self, value: str | PropertySource | None = None):
        source = GetConstantDate(value) if isinstance(value, str) else value
        super().__init__(source)

    @classmethod
    def _default_source(cls):
        return GetConstantDate()


@meta(hidden=True)
class PropertyGetVector3(PropertyGet):
    value_type = "vector3"

    def __init__(self, value=None):
        if isinstance(value, (list, tuple)) and len(value) == 3:
            value = GetConstantVector3(*value)
        super().__init__(value)

    @classmethod
    def _default_source(cls):
        return GetConstantVector3()

    def get(self, ctx):
        from polytess.core.values import ValueVector3
        try:
            return ValueVector3.coerce(super().get(ctx))
        except (TypeError, ValueError):
            return [0.0, 0.0, 0.0]


@meta(hidden=True)
class PropertyGetTransform(PropertyGet):
    value_type = "transform"

    def __init__(self, value=None):
        if isinstance(value, dict):
            source = GetConstantTransform()
            pos = value.get("pos") or [0.0, 0.0, 0.0]
            rot = value.get("rot") or [0.0, 0.0, 0.0]
            source.pos_x, source.pos_y, source.pos_z = (float(v) for v in pos)
            source.rot_x, source.rot_y, source.rot_z = (float(v) for v in rot)
            value = source
        super().__init__(value)

    @classmethod
    def _default_source(cls):
        return GetConstantTransform()

    def get(self, ctx):
        from polytess.core.values import ValueTransform
        try:
            return ValueTransform.coerce(super().get(ctx))
        except (TypeError, ValueError):
            return ValueTransform.default()


@meta(hidden=True)
class PropertyGetAny(PropertyGet):
    value_type = "any"


@meta(hidden=True)
class PropertyGetList(PropertyGet):
    """A list slot: direct entry, graph list variable or global list variable.
    ``get`` returns a plain python list — or None if the variable is missing."""

    value_type = "list"

    def __init__(self, value: str | list | PropertySource | None = None):
        # a plain string is a graph-list-variable name (builder convenience)
        if isinstance(value, str):
            value = GetGraphList(value) if value else None
        elif isinstance(value, list):
            value = GetConstantList(value)
        super().__init__(value)

    @classmethod
    def _default_source(cls):
        return GetConstantList()

    def get(self, ctx):
        return self.source.get(ctx) if self.source is not None else None


@meta(hidden=True)
class PropertyVariableRef(PropertyGet):
    """A reference to a graph/global variable or list — for events/tools that
    watch the variable itself rather than consuming its value. The source
    menu offers only variable/list reference sources (no constants)."""

    value_type = "any"

    def __init__(self, value: str | PropertySource | None = None):
        if isinstance(value, str):
            value = GetGraphVariable(value)
        super().__init__(value)

    @classmethod
    def _default_source(cls):
        return GetGraphVariable()

    @classmethod
    def compatible_sources(cls) -> list[type]:
        return [src for src in iter_subclasses(PropertySource)
                if getattr(src, "ref_kind", None) in ("variable", "list")]

    @property
    def ref_name(self) -> str:
        return getattr(self.source, "name", "") or ""

    @property
    def ref_kind(self) -> str:
        return getattr(type(self.source), "ref_kind", "variable")

    @property
    def ref_is_global(self) -> bool:
        return "Global" in type(self.source).__name__


@meta(hidden=True)
class PropertyGetTable(PropertyGet):
    """A table slot (graph or global table variable); ``get`` returns the
    live table dict or None."""

    value_type = "table"

    def __init__(self, value: str | PropertySource | None = None):
        if isinstance(value, str):
            value = GetGraphTable(value) if value else None
        super().__init__(value)

    @classmethod
    def _default_source(cls):
        return GetGraphTable()


class PropertySet(PolymorphicItem):
    """TPropertySet — wraps an exchangeable set-source."""

    value_type: str = "any"

    def __init__(self, source: SetSource | None = None):
        super().__init__()
        self.source: SetSource = source if source is not None else SetNone()

    def set(self, value: Any, ctx: Context) -> None:
        if self.source is not None:
            self.source.set(value, ctx)

    def get(self, ctx: Context) -> Any:
        return self.source.get(ctx) if self.source is not None else None

    @property
    def display(self) -> str:
        return self.source.display if self.source is not None else "(none)"

    def __str__(self) -> str:
        return self.display

    @classmethod
    def compatible_sources(cls) -> list[type]:
        out = []
        for src in iter_subclasses(SetSource):
            if cls.value_type in ("list", "table"):
                if src.value_type == cls.value_type:
                    out.append(src)
            elif cls.value_type == "any" or src.value_type in ("any", cls.value_type):
                out.append(src)
        return out


@meta(hidden=True)
class PropertySetString(PropertySet):
    value_type = "string"


@meta(hidden=True)
class PropertySetNumber(PropertySet):
    value_type = "number"


@meta(hidden=True)
class PropertySetBool(PropertySet):
    value_type = "bool"


@meta(hidden=True)
class PropertySetPath(PropertySet):
    value_type = "path"


@meta(hidden=True)
class PropertySetVector3(PropertySet):
    value_type = "vector3"


@meta(hidden=True)
class PropertySetTransform(PropertySet):
    value_type = "transform"


@meta(hidden=True)
class PropertySetAny(PropertySet):
    value_type = "any"


@meta(hidden=True)
class PropertySetList(PropertySet):
    """A writable list slot (graph or global list variable) with the list
    operations the library needs (push / clear / require / notify)."""

    value_type = "list"

    def __init__(self, value: str | SetSource | None = None):
        if isinstance(value, str):
            value = SetGraphList(value) if value else None
        super().__init__(value if value is not None else SetGraphList())

    def variable(self, ctx):
        fn = getattr(self.source, "variable", None)
        return fn(ctx) if callable(fn) else None

    def require(self, ctx, type_id: str = "string"):
        fn = getattr(self.source, "require", None)
        return fn(ctx, type_id) if callable(fn) else None

    def notify(self, ctx) -> None:
        fn = getattr(self.source, "notify", None)
        if callable(fn):
            fn(ctx)

    def push(self, value, ctx) -> None:
        fn = getattr(self.source, "push", None)
        if callable(fn):
            fn(value, ctx)

    def clear(self, ctx) -> None:
        fn = getattr(self.source, "clear", None)
        if callable(fn):
            fn(ctx)


@meta(hidden=True)
class PropertySetTable(PropertySet):
    """A writable table slot; ``get`` returns the live table dict."""

    value_type = "table"

    def __init__(self, value: str | SetSource | None = None):
        if isinstance(value, str):
            value = SetGraphTable(value) if value else None
        super().__init__(value if value is not None else SetGraphTable())

    def notify(self, ctx) -> None:
        fn = getattr(self.source, "notify", None)
        if callable(fn):
            fn(ctx)

    def ensure(self, ctx):
        fn = getattr(self.source, "ensure", None)
        return fn(ctx) if callable(fn) else None


def legacy_ref_source(prop, name: str, scope: str):
    """Map a legacy plain-string field (+ its old 'scope' sibling) to the
    matching variable source — used by serialization to migrate old graphs."""
    kind = "get" if isinstance(prop, PropertyGet) else "set"
    pairs = {
        ("get", "list"): (GetGraphList, GetGlobalList),
        ("set", "list"): (SetGraphList, SetGlobalList),
        ("get", "table"): (GetGraphTable, GetGlobalTable),
        ("set", "table"): (SetGraphTable, SetGlobalTable),
        ("get", "any"): (GetGraphVariable, GetGlobalVariable),
        ("set", "any"): (SetGraphVariable, SetGlobalVariable),
    }
    pair = pairs.get((kind, prop.value_type))
    if pair is None or not name:
        return None
    return (pair[1] if scope == "global" else pair[0])(name)
