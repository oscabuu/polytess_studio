# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Conditions — Condition / ConditionList / Branch / BranchList.

- Condition.check() applies the If/Not sign.
- ConditionList.check() combines with AND (short-circuit false) or
  OR (short-circuit true).
- Branch couples one ConditionList with one InstructionList.
- BranchList evaluates branches in order and stops at the first match
  (if / elif / else).
"""

from __future__ import annotations

from enum import Enum

from polytess.core.context import Context
from polytess.core.instructions import InstructionList
from polytess.core.metadata import meta
from polytess.core.polymorphic import PolymorphicItem


class CheckMode(str, Enum):
    AND = "and"
    OR = "or"


@meta(title="Condition", icon="diamond", color="green", hidden=True)
class Condition(PolymorphicItem):

    def __init__(self):
        super().__init__()
        self.sign: bool = True    # True = "If", False = "Not"

    # ---- overridable payload ---------------------------------------------- #

    def run(self, ctx: Context) -> bool:
        """Override in concrete conditions."""
        return True

    # ---- public check with sign -------------------------------------------- #

    def check(self, ctx: Context) -> bool:
        if not self.is_enabled:
            return self.sign
        result = bool(self.run(ctx))
        return result if self.sign else not result

    @property
    def summary(self) -> str:
        """Override to describe the condition without the If/Not prefix."""
        from polytess.core.metadata import get_meta
        return get_meta(type(self)).title

    @property
    def title(self) -> str:
        return ("If " if self.sign else "Not ") + self.summary


class ConditionList:

    def __init__(self, *conditions: Condition):
        self.conditions: list[Condition] = list(conditions)

    def check(self, ctx: Context, mode: CheckMode = CheckMode.AND) -> bool:
        mode = CheckMode(mode)
        if mode is CheckMode.AND:
            return all(c.check(ctx) for c in self.conditions)
        if not self.conditions:
            return True
        return any(c.check(ctx) for c in self.conditions)

    def __len__(self) -> int:
        return len(self.conditions)

    def __iter__(self):
        return iter(self.conditions)

    def to_data(self) -> dict:
        from polytess.core.serialization import to_data
        return {"conditions": [to_data(c) for c in self.conditions]}

    @classmethod
    def from_data(cls, data: dict) -> "ConditionList":
        from polytess.core.serialization import from_data
        obj = cls()
        obj.conditions = [from_data(c) for c in data.get("conditions", [])]
        return obj


@meta(title="Branch", icon="branch", color="green", hidden=True)
class Branch(PolymorphicItem):
    """One (conditions, instructions) pair."""

    def __init__(self, name: str = "Branch",
                 conditions: ConditionList | None = None,
                 instructions: InstructionList | None = None):
        super().__init__()
        self.name = name
        self.conditions = conditions if conditions is not None else ConditionList()
        self.instructions = instructions if instructions is not None else InstructionList()

    @property
    def title(self) -> str:
        n_c, n_i = len(self.conditions), len(self.instructions)
        return f"{self.name}  ({n_c} condition{'s' if n_c != 1 else ''}, {n_i} action{'s' if n_i != 1 else ''})"

    async def evaluate(self, ctx: Context) -> bool:
        """True if conditions matched (instructions were run)."""
        if not self.is_enabled:
            return False
        if not self.conditions.check(ctx, CheckMode.AND):
            return False
        await self.instructions.run(ctx)
        return True


class BranchList:
    """Ordered branches; the first matching branch wins (if/elif/else)."""

    def __init__(self, *branches: Branch):
        self.branches: list[Branch] = list(branches)

    async def evaluate(self, ctx: Context) -> int:
        """Runs the first matching branch; returns its index or -1."""
        for index, branch in enumerate(self.branches):
            if ctx.is_cancelled:
                return -1
            if await branch.evaluate(ctx):
                return index
        return -1

    def __len__(self) -> int:
        return len(self.branches)

    def __iter__(self):
        return iter(self.branches)

    def to_data(self) -> dict:
        from polytess.core.serialization import to_data
        return {"branches": [to_data(b) for b in self.branches]}

    @classmethod
    def from_data(cls, data: dict) -> "BranchList":
        from polytess.core.serialization import from_data
        obj = cls()
        obj.branches = [from_data(b) for b in data.get("branches", [])]
        return obj


from polytess.core.metadata import register_type  # noqa: E402

register_type(ConditionList)
register_type(BranchList)
