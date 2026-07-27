# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta


@meta(title="Variable Exists", category="Logic/Variable Exists", icon="variable",
      color="purple", description="True if the named variable is declared")
class VariableExists(Condition):
    FIELD_CHOICES = {"scope": ["graph", "global"]}

    def __init__(self, name: str = "", scope: str = "graph"):
        super().__init__()
        self.scope = scope
        self.name = name

    @property
    def summary(self) -> str:
        return f"{self.scope}:{self.name or '?'} exists"

    def run(self, ctx):
        scope = ctx.graph_variables if self.scope == "graph" else ctx.globals.variables
        return scope is not None and scope.exists(self.name)
