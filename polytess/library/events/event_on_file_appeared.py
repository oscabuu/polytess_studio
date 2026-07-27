# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Event: fires when a NEW file matching a glob pattern appears
(e.g. a solver drops a result — payload/Loop Target = the file path)."""

from __future__ import annotations

import asyncio
import glob as _glob
import os

from polytess.core.events import Event
from polytess.core.metadata import meta


@meta(title="On File Appeared", category="Files/On File Appeared", icon="file",
      color="green",
      description="Polls a glob pattern and fires once for every newly "
                  "appearing file; the path becomes the Loop Target",
      keywords=("watch", "new", "result", "glob", "monitor"))
class OnFileAppeared(Event):
    persistent = True

    def __init__(self, pattern: str = "*", poll_interval: float = 2.0,
                 ignore_existing: bool = True):
        super().__init__()
        self.pattern = pattern
        self.poll_interval = float(poll_interval)
        self.ignore_existing = bool(ignore_existing)

    @property
    def title(self) -> str:
        return f"On File Appeared {self.pattern or '?'}"

    def start(self, fire, ctx):
        super().start(fire, ctx)
        pattern = self.pattern
        if not os.path.isabs(pattern):
            pattern = os.path.join(ctx.workdir, pattern)

        async def watcher():
            seen = set(_glob.glob(pattern, recursive=True)) \
                if self.ignore_existing else set()
            while True:
                await asyncio.sleep(max(0.1, self.poll_interval))
                if self._fire is None:
                    return
                for path in sorted(_glob.glob(pattern, recursive=True)):
                    if path not in seen:
                        seen.add(path)
                        self.fire(path)

        self._task = asyncio.ensure_future(watcher())

    def stop(self):
        task = getattr(self, "_task", None)
        if task is not None:
            task.cancel()
            self._task = None
        super().stop()
