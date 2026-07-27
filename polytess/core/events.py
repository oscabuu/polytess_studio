# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Events — Event base class, adapted to the trigger-node model.

An Event decides *when* a trigger fires. The hosting TriggerNode passes a
``fire`` callback; the event arms itself in ``start`` (subscribe, schedule
timers, watch files, ...) and disarms in ``stop``.

``persistent`` distinguishes one-shot events (On Start) from long-lived
listeners (On Signal, On Timer, On File Changed) — the graph processor
keeps running as long as persistent events are armed.
"""

from __future__ import annotations

from typing import Any, Callable

from polytess.core.context import Context
from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem

FireFn = Callable[[Any], None]   # payload -> schedules the trigger's children


@meta(title="Event", icon="bolt", color="red", hidden=True)
class Event(PolymorphicItem):

    persistent: bool = False   # True: keeps listening until stop()

    def __init__(self):
        super().__init__()
        self._fire: FireFn | None = None
        self._ctx: Context | None = None

    def start(self, fire: FireFn, ctx: Context) -> None:
        """Arm the event. Store fire/ctx and subscribe to whatever source."""
        self._fire = fire
        self._ctx = ctx

    def stop(self) -> None:
        """Disarm the event; release subscriptions/tasks."""
        self._fire = None
        self._ctx = None

    def fire(self, payload: Any = None) -> None:
        if self._fire is not None and self.is_enabled:
            self._fire(payload)
