# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetAny, PropertyGetNumber, PropertyGetString
from polytess.core.signals import signals


@meta(title="Emit Signal", category="Flow/Emit Signal", icon="bolt", color="yellow",
      description="Broadcasts a signal; 'On Signal' triggers react to it",
      keywords=("event", "broadcast", "dispatch"))
class EmitSignal(Instruction):

    FIELD_HELP = {
        "signal": "Name of the signal to broadcast; every 'On Signal' "
                  "trigger listening to this name reacts to it.",
        "payload": "Optional value sent along with the signal — a literal "
                   "or any variable source; receivers can read it as the "
                   "signal's data.",
    }

    def __init__(self, signal: str = "", payload=None):
        super().__init__()
        self.signal = PropertyGetString(signal)
        self.payload = PropertyGetAny() if payload is None else payload

    @property
    def title(self) -> str:
        return f"Emit Signal {self.signal}"

    async def run(self, ctx):
        signals.emit(self.signal.get(ctx), self.payload.get(ctx))
