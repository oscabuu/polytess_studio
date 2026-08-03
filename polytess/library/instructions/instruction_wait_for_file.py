# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Wait until a file exists — the central HPC-job polling pattern."""

from __future__ import annotations

import asyncio
import os

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetNumber, PropertyGetPath


@meta(title="Wait For File", category="Flow/Wait For File", icon="clock", color="blue",
      description="Polls until the file exists (e.g. a solver result); fails "
                  "the node on timeout unless disabled",
      parameters=(("Path", "File to wait for"),
                  ("Poll Interval", "Seconds between checks"),
                  ("Timeout Hours", "0 = wait forever"),
                  ("Fail On Timeout", "Raise an error when the timeout hits")),
      keywords=("poll", "hpc", "job", "result", "exists", "monitor"))
class WaitForFile(Instruction):

    FIELD_HELP = {
        "path": "File to wait for; relative paths resolve against the "
                "working directory. The node finishes as soon as the file "
                "exists.",
        "poll_interval_s": "Seconds between existence checks (minimum "
                           "0.05 s, default 60 s). Lower values react "
                           "faster but poll more often.",
        "timeout_hours": "Maximum waiting time in hours (default 24); "
                         "0 waits forever without a deadline.",
        "fail_on_timeout": "If enabled (default), the node raises an error "
                           "when the timeout expires; if disabled, only a "
                           "warning is logged and the flow continues.",
    }

    def __init__(self, path: str = "", poll_interval_s: float = 60.0,
                 timeout_hours: float = 24.0):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.poll_interval_s = PropertyGetNumber(poll_interval_s)
        self.timeout_hours = PropertyGetNumber(timeout_hours)
        self.fail_on_timeout = PropertyGetBool(True)

    @property
    def title(self) -> str:
        return f"Wait for file {self.path} (max {self.timeout_hours} h)"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        poll = max(0.05, self.poll_interval_s.get(ctx))
        timeout_h = self.timeout_hours.get(ctx)
        deadline = asyncio.get_event_loop().time() + timeout_h * 3600 \
            if timeout_h > 0 else None
        while not os.path.exists(path):
            if self._is_cancelled(ctx):
                return
            if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                message = f"Timeout ({timeout_h:g} h) waiting for {path}"
                if self.fail_on_timeout.get(ctx):
                    raise TimeoutError(message)
                ctx.warning(message)
                return
            await asyncio.sleep(poll)
        ctx.info(f"File appeared: {path}")
