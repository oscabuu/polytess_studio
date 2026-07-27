# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

import asyncio
from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="On Timer", category="Lifecycle/On Timer", icon="clock", color="blue",
      description="Fires every N seconds (optionally limited number of times)")
class OnTimer(Event):
    persistent = True

    def __init__(self, interval: float = 5.0, repetitions: int = 0, fire_immediately: bool = False):
        super().__init__()
        self.interval = float(interval)
        self.repetitions = int(repetitions)   # 0 = unlimited
        self.fire_immediately = bool(fire_immediately)

    @property
    def title(self) -> str:
        return f"On Timer every {self.interval:g}s"

    def start(self, fire, ctx):
        super().start(fire, ctx)

        async def ticker():
            count = 0
            if self.fire_immediately:
                self.fire(count)
                count += 1
            while self.repetitions <= 0 or count < self.repetitions:
                await asyncio.sleep(max(0.05, self.interval))
                if self._fire is None:
                    return
                self.fire(count)
                count += 1

        self._task = asyncio.ensure_future(ticker())

    def stop(self):
        task = getattr(self, "_task", None)
        if task is not None:
            task.cancel()
            self._task = None
        super().stop()
