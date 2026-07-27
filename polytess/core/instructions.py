# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Instructions — Instruction / InstructionList / InstructionResult.

An InstructionList is a small sequential interpreter with a *relative*
program counter: each instruction's result says "advance by n", "stop"
or "jump", which is the foundation for skip/loop style instructions.
Execution is async (asyncio) with cooperative cancellation.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from polytess.core.context import Context
from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem

_TICK = 0.05   # cancellation poll interval for waits


class InstructionResult:
    """InstructionResult: relative next-offset + stop flag."""

    def __init__(self, next_offset: int = 1, dont_continue: bool = False):
        self.next_offset = next_offset
        self.dont_continue = dont_continue

    @classmethod
    def default(cls) -> "InstructionResult":
        return cls(1, False)

    @classmethod
    def stop(cls) -> "InstructionResult":
        return cls(0, True)

    @classmethod
    def jump(cls, offset: int) -> "InstructionResult":
        return cls(offset, False)


@meta(title="Instruction", icon="circle", color="yellow", hidden=True)
class Instruction(PolymorphicItem):

    STOP = 2 ** 31   # sentinel matching int.MaxValue

    def __init__(self):
        super().__init__()
        self._next: int = 1
        self._parent: InstructionList | None = None

    # ---- overridable payload --------------------------------------------- #

    async def run(self, ctx: Context) -> None:
        """Override in concrete instructions."""

    # ---- flow control from inside run() ----------------------------------- #

    def jump(self, offset: int) -> None:
        """Continue at current index + offset after run() returns."""
        self._next = offset

    def stop_list(self) -> None:
        """Stop the owning list after run() returns."""
        self._next = Instruction.STOP

    # ---- scheduling ----------------------------- #

    async def schedule(self, ctx: Context, parent: "InstructionList") -> InstructionResult:
        self._next = 1
        self._parent = parent
        if self.breakpoint:
            ctx.debug(f"Breakpoint reached: {self.title}")
        if self.is_enabled:
            await self.run(ctx)
        if self._is_cancelled(ctx):
            return InstructionResult.stop()
        if self._next == 1:
            return InstructionResult.default()
        if self._next == Instruction.STOP:
            return InstructionResult.stop()
        return InstructionResult.jump(self._next)

    def _is_cancelled(self, ctx: Context) -> bool:
        if ctx.is_cancelled:
            return True
        return self._parent.is_cancelled if self._parent is not None else False

    # ---- async helpers --------------------- #

    async def next_tick(self) -> None:
        await asyncio.sleep(0)

    async def wait_seconds(self, ctx: Context, seconds: float) -> None:
        end = asyncio.get_event_loop().time() + max(0.0, seconds)
        while asyncio.get_event_loop().time() < end:
            if self._is_cancelled(ctx):
                return
            await asyncio.sleep(min(_TICK, max(0.0, end - asyncio.get_event_loop().time())))

    async def wait_while(self, ctx: Context, predicate: Callable[[], bool]) -> None:
        while predicate() and not self._is_cancelled(ctx):
            await asyncio.sleep(_TICK)

    async def wait_until(self, ctx: Context, predicate: Callable[[], bool]) -> None:
        await self.wait_while(ctx, lambda: not predicate())


class InstructionList:
    """InstructionList — sequential interpreter with relative pointer."""

    def __init__(self, *instructions: Instruction):
        self.instructions: list[Instruction] = list(instructions)
        self._running_index: int = -1
        self._is_running: bool = False
        self._stopped: bool = False
        # GUI hooks
        self.on_start: list[Callable[[], None]] = []
        self.on_end: list[Callable[[], None]] = []
        self.on_step: list[Callable[[int], None]] = []

    # ---- state -------------------------------------------------------------- #

    @property
    def running_index(self) -> int:
        return self._running_index

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_cancelled(self) -> bool:
        return self._stopped

    def cancel(self) -> None:
        self._stopped = True

    def __len__(self) -> int:
        return len(self.instructions)

    def __iter__(self):
        return iter(self.instructions)

    # ---- execution ------------------------------------------------------------ #

    async def run(self, ctx: Context, from_index: int = 0) -> None:
        self._stopped = False
        self._is_running = True
        self._running_index = from_index
        for fn in list(self.on_start):
            fn()
        try:
            while 0 <= self._running_index < len(self.instructions):
                if self._stopped or ctx.is_cancelled:
                    return
                instruction = self.instructions[self._running_index]
                for fn in list(self.on_step):
                    fn(self._running_index)
                try:
                    result = await instruction.schedule(ctx, self)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    import traceback
                    ctx.error(f"{instruction.title}: {exc.__class__.__name__}: {exc}")
                    ctx.debug(traceback.format_exc())
                    raise
                if result.dont_continue:
                    return
                self._running_index += result.next_offset
        finally:
            self._is_running = False
            self._running_index = -1
            for fn in list(self.on_end):
                fn()

    # ---- editing ----------------------------------------------------------------- #

    def to_data(self) -> dict:
        from polytess.core.serialization import to_data
        return {"instructions": [to_data(i) for i in self.instructions]}

    @classmethod
    def from_data(cls, data: dict) -> "InstructionList":
        from polytess.core.serialization import from_data
        obj = cls()
        obj.instructions = [from_data(i) for i in data.get("instructions", [])]
        return obj


from polytess.core.metadata import register_type  # noqa: E402

register_type(InstructionList)
