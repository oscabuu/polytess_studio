# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction, InstructionList
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetAny, PropertyGetBool, PropertyGetNumber, PropertyGetPath,
    PropertyGetString, PropertySetAny, PropertySetBool, PropertySetNumber,
    PropertySetPath, PropertySetString,
)


@meta(title="Number Operation", category="Variables/Number Operation", icon="number",
      color="green",
      description="target = a (op) b — add, subtract, multiply, divide, power, min, max",
      keywords=("math", "arithmetic", "add", "subtract", "multiply", "divide"))
class NumberOperation(Instruction):
    FIELD_CHOICES = {"operation": ["+", "-", "*", "/", "%", "**", "min", "max"]}

    def __init__(self, target=None, a: float = 0.0, operation: str = "+", b: float = 0.0):
        super().__init__()
        self.target = target if target is not None else PropertySetNumber()
        self.a = PropertyGetNumber(a)
        self.operation = operation
        self.b = PropertyGetNumber(b)

    @property
    def title(self) -> str:
        return f"Set {self.target} = {self.a} {self.operation} {self.b}"

    async def run(self, ctx):
        a, b = self.a.get(ctx), self.b.get(ctx)
        op = self.operation
        if op == "+":
            result = a + b
        elif op == "-":
            result = a - b
        elif op == "*":
            result = a * b
        elif op == "/":
            result = a / b if b != 0 else 0.0
        elif op == "%":
            result = a % b if b != 0 else 0.0
        elif op == "**":
            result = a ** b
        elif op == "min":
            result = min(a, b)
        else:
            result = max(a, b)
        self.target.set(result, ctx)
