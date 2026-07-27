# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetNumber, PropertyGetString

_NUM_OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


@meta(title="Compare Number", category="Math/Compare Number", icon="number", color="green",
      description="Compares two numbers", keywords=("equals", "greater", "less"))
class CompareNumber(Condition):
    FIELD_CHOICES = {"comparison": list(_NUM_OPS)}

    def __init__(self, a: float = 0.0, comparison: str = "=", b: float = 0.0):
        super().__init__()
        self.a = PropertyGetNumber(a)
        self.comparison = comparison
        self.b = PropertyGetNumber(b)

    @property
    def summary(self) -> str:
        return f"{self.a} {self.comparison} {self.b}"

    def run(self, ctx):
        return _NUM_OPS.get(self.comparison, _NUM_OPS["="])(self.a.get(ctx), self.b.get(ctx))
