# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Variables .:

- Graph variables
- Global variables

Name variables are typed named slots; list variables are named homogeneous
lists. Both emit change events for the GUI blackboard.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Iterable

from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem
from polytess.core.values import Value, ValueNull, create_value, value_from_python


@meta(title="Name Variable", icon="variable", color="purple", hidden=True)
class NameVariable(PolymorphicItem):
    """A named, typed value slot."""

    def __init__(self, name: str = "", value: Value | None = None):
        super().__init__()
        self.name = name
        self.value: Value = value if value is not None else ValueNull()

    @property
    def type_id(self) -> str:
        return self.value.type_id

    @property
    def title(self) -> str:
        return f"{self.name} = {self.value.get()!r}"


class NameVariables:
    """Ordered collection of NameVariable with change events."""

    def __init__(self):
        self._items: dict[str, NameVariable] = {}
        self.on_change: list[Callable[[str], None]] = []

    # -- declaration -------------------------------------------------------- #

    def declare(self, name: str, type_id: str = "string", value: Any = None) -> NameVariable:
        var = NameVariable(name, create_value(type_id, value))
        self._items[name] = var
        self._emit(name)
        return var

    def add(self, var: NameVariable) -> None:
        self._items[var.name] = var
        self._emit(var.name)

    def remove(self, name: str) -> None:
        if self._items.pop(name, None) is not None:
            self._emit(name)

    def rename(self, old: str, new: str) -> None:
        if old in self._items and new and new not in self._items:
            var = self._items.pop(old)
            var.name = new
            self._items[new] = var
            self._emit(old)
            self._emit(new)

    # -- access --------------------------------------------------------------- #

    def exists(self, name: str) -> bool:
        return name in self._items

    def variable(self, name: str) -> NameVariable | None:
        return self._items.get(name)

    def get(self, name: str, default: Any = None) -> Any:
        var = self._items.get(name)
        return var.value.get() if var is not None else default

    def set(self, name: str, value: Any) -> None:
        var = self._items.get(name)
        if var is None or isinstance(var.value, ValueNull):
            wrapped = value_from_python(value)
            if var is None:
                var = NameVariable(name, wrapped)
                self._items[name] = var
            else:
                var.value = wrapped
        else:
            var.value.set(value)
        self._emit(name)

    def names(self) -> list[str]:
        return list(self._items)

    def __iter__(self) -> Iterable[NameVariable]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def _emit(self, name: str) -> None:
        for fn in list(self.on_change):
            fn(name)

    # -- serialization ------------------------------------------------------- #

    def to_data(self) -> dict:
        from polytess.core.serialization import to_data
        return {"items": [to_data(v) for v in self._items.values()]}

    @classmethod
    def from_data(cls, data: dict) -> "NameVariables":
        from polytess.core.serialization import from_data
        obj = cls()
        for item in data.get("items", []):
            var = from_data(item)
            obj._items[var.name] = var
        return obj


@meta(title="List Variable", icon="list", color="purple", hidden=True)
class ListVariable(PolymorphicItem):
    """A named homogeneous list.

    Items are plain Python values; ``type_id`` declares the element type."""

    def __init__(self, name: str = "", type_id: str = "string", items: list | None = None):
        super().__init__()
        self.name = name
        self.type_id = type_id
        self.items: list = list(items) if items else []

    @property
    def title(self) -> str:
        return f"{self.name} [{len(self.items)}]"

    # change kinds mirror ListVariableRuntime.Change
    def _coerce(self, value: Any) -> Any:
        return create_value(self.type_id, value).get()

    def get(self, index: int, default: Any = None) -> Any:
        if -len(self.items) <= index < len(self.items):
            return self.items[index]
        return default

    def set(self, index: int, value: Any) -> None:
        self.items[index] = self._coerce(value)

    def push(self, value: Any) -> None:
        self.items.append(self._coerce(value))

    def insert(self, index: int, value: Any) -> None:
        self.items.insert(index, self._coerce(value))

    def remove_at(self, index: int) -> None:
        del self.items[index]

    def move(self, src: int, dst: int) -> None:
        self.items.insert(dst, self.items.pop(src))

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)


class ListVariables:
    """Named collection of ListVariable with change events."""

    def __init__(self):
        self._items: dict[str, ListVariable] = {}
        self.on_change: list[Callable[[str], None]] = []

    def declare(self, name: str, type_id: str = "string", items: list | None = None) -> ListVariable:
        lst = ListVariable(name, type_id, items)
        self._items[name] = lst
        self._emit(name)
        return lst

    def remove(self, name: str) -> None:
        if self._items.pop(name, None) is not None:
            self._emit(name)

    def rename(self, old: str, new: str) -> None:
        if old in self._items and new and new not in self._items:
            lst = self._items.pop(old)
            lst.name = new
            self._items[new] = lst
            self._emit(old)
            self._emit(new)

    def exists(self, name: str) -> bool:
        return name in self._items

    def get(self, name: str) -> ListVariable | None:
        return self._items.get(name)

    def require(self, name: str, type_id: str = "string") -> ListVariable:
        lst = self._items.get(name)
        if lst is None:
            lst = self.declare(name, type_id)
        return lst

    def names(self) -> list[str]:
        return list(self._items)

    def notify(self, name: str) -> None:
        self._emit(name)

    def __iter__(self) -> Iterable[ListVariable]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def _emit(self, name: str) -> None:
        for fn in list(self.on_change):
            fn(name)

    def to_data(self) -> dict:
        from polytess.core.serialization import to_data
        return {"items": [to_data(v) for v in self._items.values()]}

    @classmethod
    def from_data(cls, data: dict) -> "ListVariables":
        from polytess.core.serialization import from_data
        obj = cls()
        for item in data.get("items", []):
            lst = from_data(item)
            obj._items[lst.name] = lst
        return obj


from polytess.core.metadata import register_type  # noqa: E402

register_type(NameVariables)
register_type(ListVariables)


class GlobalScope:
    """Application-wide variables.

    Can be persisted to a project JSON file."""

    _instance: "GlobalScope | None" = None

    def __init__(self):
        self.variables = NameVariables()
        self.lists = ListVariables()

    @classmethod
    def instance(cls) -> "GlobalScope":
        if cls._instance is None:
            cls._instance = GlobalScope()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    # -- persistence -------------------------------------------------------- #

    def save(self, path: str) -> None:
        from polytess.core.serialization import to_data
        data = {"variables": to_data(self.variables), "lists": to_data(self.lists)}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def load(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.variables = NameVariables.from_data(data.get("variables", {}))
        self.lists = ListVariables.from_data(data.get("lists", {}))
