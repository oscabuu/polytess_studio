# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""TValue port — typed value boxes with a type-id registry.

 TValue + ValueString/ValueNumber(double)/ValueBool/... each registering
itself in LUTs (type_id -> factory, python type -> type_id)."""

from __future__ import annotations

from typing import Any

from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem

_BY_ID: dict[str, type["Value"]] = {}
_ID_BY_PYTYPE: dict[type, str] = {}


class Value(PolymorphicItem):
    type_id: str = ""
    py_type: type = object

    def __init__(self, value: Any = None):
        super().__init__()
        self.value = self.coerce(value) if value is not None else self.default()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.type_id:
            _BY_ID[cls.type_id] = cls
            _ID_BY_PYTYPE.setdefault(cls.py_type, cls.type_id)

    # -- override per type -------------------------------------------------- #

    @classmethod
    def default(cls) -> Any:
        return None

    @classmethod
    def coerce(cls, value: Any) -> Any:
        return value

    # -- common -------------------------------------------------------------- #

    def get(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        self.value = self.coerce(value)

    @property
    def title(self) -> str:
        return f"{super().title}: {self.value!r}"


@meta(title="Null", category="Values/Null", icon="null", color="text-light",
      description="An empty value without a type")
class ValueNull(Value):
    type_id = "null"
    py_type = type(None)

    @classmethod
    def coerce(cls, value):
        return None


@meta(title="Boolean", category="Values/Boolean", icon="toggle", color="red",
      description="A true/false value", keywords=("bool", "flag"))
class ValueBool(Value):
    type_id = "bool"
    py_type = bool

    @classmethod
    def default(cls):
        return False

    @classmethod
    def coerce(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)


@meta(title="Number", category="Values/Number", icon="number", color="green",
      description="A floating point number (double precision)", keywords=("float", "double", "int"))
class ValueNumber(Value):
    type_id = "number"
    py_type = float

    @classmethod
    def default(cls):
        return 0.0

    @classmethod
    def coerce(cls, value):
        return float(value)


@meta(title="Integer", category="Values/Integer", icon="number", color="teal",
      description="A whole number", keywords=("int", "count", "index"))
class ValueInteger(Value):
    type_id = "integer"
    py_type = int

    @classmethod
    def default(cls):
        return 0

    @classmethod
    def coerce(cls, value):
        if isinstance(value, str):
            value = float(value) if value.strip() else 0
        return int(value)


@meta(title="String", category="Values/String", icon="string", color="yellow",
      description="A string of characters", keywords=("text",))
class ValueString(Value):
    type_id = "string"
    py_type = str

    @classmethod
    def default(cls):
        return ""

    @classmethod
    def coerce(cls, value):
        return "" if value is None else str(value)


@meta(title="Path", category="Values/Path", icon="folder", color="blue",
      description="A file or directory path", keywords=("file", "folder", "directory"))
class ValuePath(Value):
    type_id = "path"
    py_type = str

    @classmethod
    def default(cls):
        return ""

    @classmethod
    def coerce(cls, value):
        return "" if value is None else str(value)


@meta(title="Date", category="Values/Date", icon="clock", color="teal",
      description="A date/time, stored as 'YYYY-MM-DD HH:MM:SS' (input also "
                  "accepts ISO-8601 and DD.MM.YYYY formats)",
      keywords=("time", "datetime", "schedule", "deadline"))
class ValueDate(Value):
    type_id = "date"
    py_type = str

    @classmethod
    def default(cls):
        return ""          # empty = not set

    @classmethod
    def coerce(cls, value):
        from polytess.core.dates import format_date, parse_date
        if value is None or value == "":
            return ""
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f"not a date: {value!r}")
        return format_date(parsed)


@meta(title="Table", category="Values/Table", icon="list", color="pink",
      description="Tabular data (rows of named columns) — CSV configs, "
                  "DOE matrices, job-status tables")
class ValueTable(Value):
    type_id = "table"
    py_type = dict

    @classmethod
    def default(cls):
        from polytess.core.tables import new_table
        return new_table()

    @classmethod
    def coerce(cls, value):
        from polytess.core.tables import coerce_table
        return coerce_table(value)

    @property
    def title(self) -> str:
        from polytess.core.tables import summary
        return f"Table: {summary(self.value)}"


@meta(title="List", category="Values/List", icon="list", color="purple",
      description="An ordered list of plain values")
class ValueList(Value):
    type_id = "list"
    py_type = list

    @classmethod
    def default(cls):
        return []

    @classmethod
    def coerce(cls, value):
        return list(value)


def _parse_floats(text: str, count: int) -> list[float]:
    """'1; 2, 3' / '(1 2 3)' -> [1.0, 2.0, 3.0] — raises on wrong arity."""
    cleaned = text.strip().strip("()[]{}")
    for sep in (";", ","):
        cleaned = cleaned.replace(sep, " ")
    parts = [p for p in cleaned.split() if p]
    if len(parts) != count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return [float(p) for p in parts]


def _coerce_vector3(value) -> list[float]:
    if value is None or value == "":
        return [0.0, 0.0, 0.0]
    if isinstance(value, str):
        return _parse_floats(value, 3)
    if isinstance(value, dict):
        return [float(value.get(k, 0.0)) for k in ("x", "y", "z")]
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return [float(v) for v in value]
    raise ValueError(f"not a vector3: {value!r}")


def format_vector3(vec: list[float]) -> str:
    return ", ".join(f"{v:g}" for v in vec)


@meta(title="Vector3", category="Values/Vector3", icon="axes", color="green",
      description="Three numbers (x, y, z) — positions, rotations, directions; "
                  "enter as 'x, y, z'",
      keywords=("position", "direction", "xyz", "coordinates"))
class ValueVector3(Value):
    type_id = "vector3"
    py_type = list

    @classmethod
    def default(cls):
        return [0.0, 0.0, 0.0]

    @classmethod
    def coerce(cls, value):
        return _coerce_vector3(value)

    @property
    def title(self) -> str:
        return f"Vector3: ({format_vector3(self.value)})"


@meta(title="Transform", category="Values/Transform", icon="transform", color="teal",
      description="Position + rotation, each a Vector3 — enter as "
                  "'px, py, pz | rx, ry, rz'",
      keywords=("pose", "position", "rotation", "placement"))
class ValueTransform(Value):
    type_id = "transform"
    py_type = dict

    @classmethod
    def default(cls):
        return {"pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0]}

    @classmethod
    def coerce(cls, value):
        if value is None or value == "":
            return cls.default()
        if isinstance(value, str):
            head, sep, tail = value.partition("|")
            pos = _coerce_vector3(head)
            rot = _coerce_vector3(tail) if sep else [0.0, 0.0, 0.0]
            return {"pos": pos, "rot": rot}
        if isinstance(value, dict):
            return {"pos": _coerce_vector3(value.get("pos")),
                    "rot": _coerce_vector3(value.get("rot"))}
        raise ValueError(f"not a transform: {value!r}")

    @property
    def title(self) -> str:
        return (f"Transform: pos ({format_vector3(self.value['pos'])}) · "
                f"rot ({format_vector3(self.value['rot'])})")



def value_types() -> dict[str, type[Value]]:
    return dict(_BY_ID)


def create_value(type_id: str, value: Any = None) -> Value:
    cls = _BY_ID.get(type_id, ValueNull)
    return cls(value)


def value_from_python(obj: Any) -> Value:
    """Wrap a plain Python object in the matching Value."""
    import datetime as _dt
    if obj is None:
        return ValueNull()
    if isinstance(obj, _dt.datetime):
        return ValueDate(obj)
    if isinstance(obj, bool):
        return ValueBool(obj)
    if isinstance(obj, int):
        return ValueInteger(obj)
    if isinstance(obj, float):
        return ValueNumber(obj)
    if isinstance(obj, str):
        return ValueString(obj)
    if isinstance(obj, (list, tuple)):
        return ValueList(list(obj))
    return ValueString(str(obj))
