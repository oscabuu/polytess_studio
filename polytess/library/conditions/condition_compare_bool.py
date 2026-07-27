# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetNumber, PropertyGetString


@meta(title="Compare Boolean", category="Math/Compare Boolean", icon="toggle", color="red",
      description="Checks a true/false value", keywords=("flag", "is"))
class CompareBool(Condition):

    def __init__(self, value: bool = True, compare_to: bool = True):
        super().__init__()
        self.value = PropertyGetBool(value)
        self.compare_to = PropertyGetBool(compare_to)

    @property
    def summary(self) -> str:
        return f"{self.value} is {self.compare_to}"

    def run(self, ctx):
        return self.value.get(ctx) == self.compare_to.get(ctx)
