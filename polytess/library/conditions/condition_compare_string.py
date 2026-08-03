# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetNumber, PropertyGetString


@meta(title="Compare String", category="Math/Compare String", icon="string", color="yellow",
      description="Compares two strings", keywords=("equals", "contains", "starts", "ends"))
class CompareString(Condition):
    FIELD_CHOICES = {"comparison": ["equals", "different", "contains",
                                    "starts-with", "ends-with"]}

    FIELD_HELP = {
        "a": "Left-hand string of the comparison; can come from a "
             "variable source.",
        "comparison": "How A is tested against B: \"equals\" exact match, "
                      "\"different\" not equal, \"contains\" B occurs in "
                      "A, \"starts-with\" A begins with B, \"ends-with\" "
                      "A ends with B. Case-sensitive.",
        "b": "Right-hand string of the comparison; can come from a "
             "variable source.",
        "sign": "Polarity of the check: enabled means \"If\" (result used "
                "as is), disabled means \"Not\" (result inverted).",
    }

    def __init__(self, a: str = "", comparison: str = "equals", b: str = ""):
        super().__init__()
        self.a = PropertyGetString(a)
        self.comparison = comparison
        self.b = PropertyGetString(b)

    @property
    def summary(self) -> str:
        return f"{self.a} {self.comparison} {self.b}"

    def run(self, ctx):
        a, b = self.a.get(ctx), self.b.get(ctx)
        return {
            "equals": a == b,
            "different": a != b,
            "contains": b in a,
            "starts-with": a.startswith(b),
            "ends-with": a.endswith(b),
        }.get(self.comparison, a == b)
