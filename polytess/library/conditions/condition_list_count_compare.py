# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetList, PropertyGetNumber

_NUM_OPS = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


@meta(title="List Count", category="Math/List Count", icon="list", color="purple",
      description="Compares the number of elements in a list")
class ListCountCompare(Condition):
    FIELD_CHOICES = {"comparison": list(_NUM_OPS)}

    FIELD_HELP = {
        "list": "List variable whose element count is tested; a missing "
                "list counts as 0 elements.",
        "comparison": "Operator applied as count <op> value: \"=\" equal, "
                      "\"!=\" not equal, \"<\" less, \"<=\" less or "
                      "equal, \">\" greater, \">=\" greater or equal.",
        "count": "Number the list length is compared against (default 0).",
        "sign": "Polarity of the check: enabled means \"If\" (result used "
                "as is), disabled means \"Not\" (result inverted).",
    }

    LEGACY_ALIASES = {"list_name": "list"}

    def __init__(self, list_name: str | list = "", comparison: str = ">",
                 count: float = 0.0):
        super().__init__()
        self.list = PropertyGetList(list_name)
        self.comparison = comparison
        self.count = PropertyGetNumber(count)

    @property
    def summary(self) -> str:
        return f"len({self.list.display}) {self.comparison} {self.count}"

    def run(self, ctx):
        items = self.list.get(ctx)
        length = float(len(items)) if items is not None else 0.0
        return _NUM_OPS.get(self.comparison, _NUM_OPS["="])(length, self.count.get(ctx))
