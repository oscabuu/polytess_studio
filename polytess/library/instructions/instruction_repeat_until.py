# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Generic retry / polling loop: run nested actions until conditions hold."""

from __future__ import annotations

from polytess.core.conditions import CheckMode, ConditionList
from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetNumber


@meta(title="Repeat Until", category="Flow/Repeat Until", icon="repeat", color="yellow",
      description="Runs the nested actions, then checks the conditions; repeats "
                  "(with delay) until they hold or the attempt limit is reached. "
                  "The attempt number (1-based) is the Loop Target.",
      parameters=(("Max Attempts", "0 = unlimited"),
                  ("Delay", "Seconds between attempts"),
                  ("Fail On Max", "Raise when the limit is reached")),
      keywords=("retry", "poll", "loop", "while", "until", "attempts"))
class RepeatUntil(Instruction):

    def __init__(self, max_attempts: int = 5, delay_s: float = 1.0):
        super().__init__()
        self.actions = InstructionList()
        self.conditions = ConditionList()
        self.max_attempts = PropertyGetNumber(max_attempts)
        self.delay_s = PropertyGetNumber(delay_s)
        self.fail_on_max = PropertyGetBool(True)

    @property
    def title(self) -> str:
        return f"Repeat until ({len(self.conditions)} conditions, " \
               f"max {self.max_attempts} attempts)"

    async def run(self, ctx):
        max_attempts = int(self.max_attempts.get(ctx))
        delay = max(0.0, self.delay_s.get(ctx))
        attempt = 0
        while True:
            attempt += 1
            if self._is_cancelled(ctx):
                return
            attempt_ctx = ctx.child(target=attempt)
            try:
                await self.actions.run(attempt_ctx)
                if self.conditions.check(attempt_ctx, CheckMode.AND):
                    if attempt > 1:
                        ctx.info(f"Repeat Until: succeeded on attempt {attempt}")
                    return
            except Exception as exc:
                ctx.warning(f"Repeat Until: attempt {attempt} failed: {exc}")
            if max_attempts > 0 and attempt >= max_attempts:
                message = f"Repeat Until: giving up after {attempt} attempts"
                if self.fail_on_max.get(ctx):
                    raise RuntimeError(message)
                ctx.warning(message)
                return
            if delay:
                await self.wait_seconds(ctx, delay)
