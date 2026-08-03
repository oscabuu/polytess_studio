# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import asyncio
import os
from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="On File Changed", category="Files/On File Changed", icon="file", color="blue",
      description="Polls a file and fires when its modification time changes "
                  "(e.g. solver wrote new results); path becomes the Loop Target")
class OnFileChanged(Event):
    persistent = True

    FIELD_HELP = {
        "path": "File to watch; relative paths resolve against the "
                "working directory. Fires whenever the modification time "
                "changes (also on create/delete); the path becomes the "
                "Loop Target of the triggered flow.",
        "poll_interval": "Seconds between modification-time checks "
                         "(default 1.0, minimum 0.1).",
    }

    def __init__(self, path: str = "", poll_interval: float = 1.0):
        super().__init__()
        self.path = path
        self.poll_interval = float(poll_interval)

    @property
    def title(self) -> str:
        return f"On File Changed {os.path.basename(self.path) or '?'}"

    def start(self, fire, ctx):
        super().start(fire, ctx)
        path = ctx.resolve_path(self.path)

        async def watcher():
            last = os.path.getmtime(path) if os.path.exists(path) else None
            while True:
                await asyncio.sleep(max(0.1, self.poll_interval))
                if self._fire is None:
                    return
                current = os.path.getmtime(path) if os.path.exists(path) else None
                if current != last:
                    last = current
                    self.fire(path)

        self._task = asyncio.ensure_future(watcher())

    def stop(self):
        task = getattr(self, "_task", None)
        if task is not None:
            task.cancel()
            self._task = None
        super().stop()
