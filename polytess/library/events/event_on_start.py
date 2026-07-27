# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="On Start", category="Lifecycle/On Start", icon="play", color="green",
      description="Fires once when the workflow starts")
class OnStart(Event):
    persistent = False

    def start(self, fire, ctx):
        super().start(fire, ctx)
        self.fire()
