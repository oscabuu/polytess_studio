# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Tagged-JSON serialization for polymorphic objects.

Rules:
- primitives / lists / dicts pass through,
- registered polymorphic objects become {"$type": <type name>, <public fields>},
- instance attributes starting with "_" are runtime state and are skipped,
- classes may customize via ``to_data(self) -> dict`` / ``from_data(cls, data)``,
- all serializable classes must be constructible with no arguments,
- unknown fields in the data are ignored; ``LEGACY_ALIASES = {old: new}`` on a
  class remaps renamed fields, and a plain string arriving in a field that is
  now a PropertyGet/Set becomes the matching variable source (old graphs with
  scope + name pairs keep loading).
"""

from __future__ import annotations

import json
from typing import Any

from polytess.core.metadata import resolve_type, type_name_of


def _is_property(obj: Any) -> bool:
    from polytess.core.properties import PropertyGet, PropertySet
    return isinstance(obj, (PropertyGet, PropertySet))


def to_data(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_data(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): to_data(v) for k, v in obj.items()}
    custom = getattr(obj, "to_data", None)
    if callable(custom):
        data = custom()
    else:
        data = {k: to_data(v) for k, v in vars(obj).items() if not k.startswith("_")}
    data["$type"] = type_name_of(type(obj))
    return data


def from_data(data: Any) -> Any:
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, list):
        return [from_data(v) for v in data]
    if isinstance(data, dict):
        if "$type" not in data:
            return {k: from_data(v) for k, v in data.items()}
        cls = resolve_type(data["$type"])
        custom = getattr(cls, "from_data", None)
        if callable(custom):
            return custom({k: v for k, v in data.items() if k != "$type"})
        obj = cls()
        aliases = getattr(cls, "LEGACY_ALIASES", None) or {}
        scope_hint = data.get("scope") if isinstance(data.get("scope"), str) else "graph"
        for key, value in data.items():
            if key == "$type":
                continue
            key = aliases.get(key, key)
            if not hasattr(obj, key):     # legacy/unknown field — ignore
                continue
            incoming = from_data(value)
            current = getattr(obj, key, None)
            if _is_property(current) and isinstance(incoming, str):
                # legacy plain name string for a field that is now a
                # property: turn it into the matching variable source
                from polytess.core.properties import legacy_ref_source
                source = legacy_ref_source(current, incoming, scope_hint)
                if source is not None:
                    current.source = source
                continue
            setattr(obj, key, incoming)
        return obj
    raise TypeError(f"Cannot deserialize {type(data).__name__}")


def dumps(obj: Any, indent: int = 2) -> str:
    return json.dumps(to_data(obj), indent=indent, ensure_ascii=False)


def loads(text: str) -> Any:
    return from_data(json.loads(text))
