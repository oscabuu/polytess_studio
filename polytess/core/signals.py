# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Signals — global publish/subscribe hub
(Signals.Subscribe / Unsubscribe / Emit)."""

from __future__ import annotations

from typing import Any, Callable

Receiver = Callable[[str, Any], None]   # (signal_name, payload)


class SignalHub:

    def __init__(self):
        self._receivers: dict[str, list[Receiver]] = {}

    def subscribe(self, signal: str, receiver: Receiver) -> None:
        self._receivers.setdefault(signal, []).append(receiver)

    def unsubscribe(self, signal: str, receiver: Receiver) -> None:
        listeners = self._receivers.get(signal)
        if listeners and receiver in listeners:
            listeners.remove(receiver)
            if not listeners:
                del self._receivers[signal]

    def emit(self, signal: str, payload: Any = None) -> int:
        listeners = list(self._receivers.get(signal, ()))
        for receiver in listeners:
            receiver(signal, payload)
        return len(listeners)

    def clear(self) -> None:
        self._receivers.clear()


# Global hub
signals = SignalHub()
