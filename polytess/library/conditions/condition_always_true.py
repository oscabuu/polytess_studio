# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta


@meta(title="Always True", category="Logic/Always True", icon="check", color="green",
      description="Always evaluates to true")
class AlwaysTrue(Condition):

    @property
    def summary(self) -> str:
        return "always true"

    def run(self, ctx):
        return True
