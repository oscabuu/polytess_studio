# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Fire a trigger whenever a graph/global variable (or list) changes."""

from __future__ import annotations

import copy

from polytess.core.events import Event
from polytess.core.metadata import meta
from polytess.core.properties import PropertyVariableRef

_MISSING = object()


@meta(title="On Variable Changed", category="Logic/On Variable Changed",
      icon="variable", color="purple",
      description="Fires whenever the chosen graph/global variable (or list) "
                  "changes; the new value becomes the Loop Target. With an "
                  "empty variable name it fires on ANY change in the chosen "
                  "scope and the changed variable's name is the Loop Target.",
      parameters=(("Variable", "The variable/list to watch"),
                  ("Only On Change", "Skip writes that keep the value "
                   "identical (also breaks self-triggering loops)")),
      keywords=("watch", "observe", "blackboard", "reactive", "change"))
class OnVariableChanged(Event):
    persistent = True

    def __init__(self, name: str = ""):
        super().__init__()
        self.variable = PropertyVariableRef(name)
        self.only_on_change = True

    @property
    def title(self) -> str:
        name = self.variable.ref_name
        scope = "global" if self.variable.ref_is_global else "graph"
        return f"On Variable Changed {name or f'(any {scope})'}"

    # ------------------------------------------------------------------ #

    def _collection(self, ctx):
        if self.variable.ref_kind == "list":
            return ctx.globals.lists if self.variable.ref_is_global \
                else ctx.graph_lists
        return ctx.globals.variables if self.variable.ref_is_global \
            else ctx.graph_variables

    def _value_of(self, collection, name: str):
        if self.variable.ref_kind == "list":
            lst = collection.get(name)
            return list(lst.items) if lst is not None else _MISSING
        if not collection.exists(name):
            return _MISSING
        return collection.get(name)

    def _snapshot(self, collection, name: str):
        value = self._value_of(collection, name)
        # tables/lists are mutated in place — keep an independent copy,
        # otherwise "previous" and "current" would always compare equal
        return value if value is _MISSING else copy.deepcopy(value)

    def start(self, fire, ctx):
        super().start(fire, ctx)
        collection = self._collection(ctx)
        if collection is None:
            ctx.warning("On Variable Changed: no variable scope available")
            return
        watch = self.variable.ref_name
        self._last = {}
        if self.only_on_change:
            names = [watch] if watch else [v.name for v in collection]
            for name in names:
                self._last[name] = self._snapshot(collection, name)

        def on_change(changed_name: str) -> None:
            if self._fire is None:
                return
            if watch and changed_name != watch:
                return
            value = self._value_of(collection, changed_name)
            if self.only_on_change:
                previous = self._last.get(changed_name, _MISSING)
                current = _MISSING if value is _MISSING else copy.deepcopy(value)
                self._last[changed_name] = current
                if previous is not _MISSING and previous == value:
                    return
            payload = changed_name if not watch \
                else (None if value is _MISSING else value)
            self.fire(payload)

        self._collection_ref = collection
        self._callback = on_change
        collection.on_change.append(on_change)

    def stop(self):
        collection = getattr(self, "_collection_ref", None)
        callback = getattr(self, "_callback", None)
        if collection is not None and callback in collection.on_change:
            collection.on_change.remove(callback)
        self._collection_ref = None
        self._callback = None
        super().stop()
