# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Wait until ALL files of a list variable exist (fan-in barrier)."""

from __future__ import annotations

import asyncio
import os

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetBool, PropertyGetList,
                                    PropertyGetNumber)


@meta(title="Wait For Files", category="Flow/Wait For Files", icon="clock", color="blue",
      description="Polls until every path in a list exists — the "
                  "fan-in after submitting a batch of jobs",
      keywords=("poll", "barrier", "all", "jobs", "batch"))
class WaitForFiles(Instruction):

    FIELD_HELP = {
        "list": "List variable holding the paths to wait for; relative "
                "paths resolve against the working directory. The node "
                "finishes once every listed file exists.",
        "poll_interval_s": "Seconds between existence checks (minimum "
                           "0.05 s, default 60 s).",
        "timeout_hours": "Maximum waiting time in hours (default 24); "
                         "0 waits forever without a deadline.",
        "fail_on_timeout": "If enabled (default), the node raises an error "
                           "when the timeout expires; if disabled, only a "
                           "warning is logged and the flow continues.",
    }

    LEGACY_ALIASES = {"list_name": "list"}

    def __init__(self, list_name: str | list = "", poll_interval_s: float = 60.0,
                 timeout_hours: float = 24.0):
        super().__init__()
        self.list = PropertyGetList(list_name)
        self.poll_interval_s = PropertyGetNumber(poll_interval_s)
        self.timeout_hours = PropertyGetNumber(timeout_hours)
        self.fail_on_timeout = PropertyGetBool(True)

    @property
    def title(self) -> str:
        return f"Wait for all files in {self.list.display}"

    async def run(self, ctx):
        items = self.list.get(ctx)
        if items is None:
            ctx.warning(f"Wait For Files: list {self.list.display} not found")
            return
        paths = [ctx.resolve_path(str(p)) for p in items]
        poll = max(0.05, self.poll_interval_s.get(ctx))
        timeout_h = self.timeout_hours.get(ctx)
        deadline = asyncio.get_event_loop().time() + timeout_h * 3600 \
            if timeout_h > 0 else None
        while True:
            missing = [p for p in paths if not os.path.exists(p)]
            if not missing:
                ctx.info(f"All {len(paths)} files present")
                return
            if self._is_cancelled(ctx):
                return
            if deadline is not None and asyncio.get_event_loop().time() >= deadline:
                message = (f"Timeout ({timeout_h:g} h): {len(missing)} of "
                           f"{len(paths)} files still missing, e.g. {missing[0]}")
                if self.fail_on_timeout.get(ctx):
                    raise TimeoutError(message)
                ctx.warning(message)
                return
            await asyncio.sleep(poll)
