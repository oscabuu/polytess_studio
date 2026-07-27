# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.events import Event
from polytess.core.metadata import meta
from polytess.core.signals import signals


@meta(title="On Signal", category="Logic/On Signal", icon="bolt", color="yellow",
      description="Fires whenever the given signal is emitted (Emit Signal); "
                  "the payload becomes the Loop Target",
      keywords=("receive", "event", "broadcast"))
class OnSignal(Event):
    persistent = True

    def __init__(self, signal: str = ""):
        super().__init__()
        self.signal = signal

    @property
    def title(self) -> str:
        return f"On Signal {self.signal or '?'}"

    def start(self, fire, ctx):
        super().start(fire, ctx)

        def receiver(name, payload):
            self.fire(payload)

        self._receiver = receiver
        signals.subscribe(self.signal, receiver)

    def stop(self):
        receiver = getattr(self, "_receiver", None)
        if receiver is not None:
            signals.unsubscribe(self.signal, receiver)
            self._receiver = None
        super().stop()
