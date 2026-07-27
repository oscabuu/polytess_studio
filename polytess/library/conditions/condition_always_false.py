# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.conditions import Condition
from polytess.core.metadata import meta


@meta(title="Always False", category="Logic/Always False", icon="cancel", color="red",
      description="Always evaluates to false")
class AlwaysFalse(Condition):

    @property
    def summary(self) -> str:
        return "always false"

    def run(self, ctx):
        return False
