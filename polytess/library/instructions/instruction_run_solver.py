# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Run the configured MKS or FEM solver (Settings → Solvers)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetNumber, PropertyGetString,
                                      PropertySetNumber, PropertySetString)
from polytess.core.shell import run_solver, solver_profile


@meta(title="Run Solver", category="Process/Run Solver", icon="terminal",
      color="teal",
      description="Runs the MKS (Simpack) or FEM (Abaqus) solver as "
                  "configured in Settings → Solvers — locally or via SSH "
                  "with the right shell wrapping and path mapping",
      parameters=(("Solver", "Which profile to use: mks or fem"),
                  ("Arguments", "Appended to the configured solver command"),
                  ("Command Override", "Replaces the configured command "
                                       "(empty = use Settings)"),
                  ("Timeout Hours", "0 = no timeout")),
      keywords=("solver", "simpack", "abaqus", "mks", "fem", "ssh"))
class RunSolver(Instruction):

    FIELD_CHOICES = {"solver": ["fem", "mks"]}

    def __init__(self, solver: str = "fem", arguments: str = ""):
        super().__init__()
        self.solver = solver
        self.arguments = PropertyGetString(arguments)
        self.command_override = PropertyGetString("")
        self.timeout_hours = PropertyGetNumber(0.0)
        self.exit_code_to = PropertySetNumber()
        self.output_to = PropertySetString()

    @property
    def title(self) -> str:
        return f"Run {self.solver.upper()} solver {self.arguments}"

    async def run(self, ctx) -> None:
        override = self.command_override.get(ctx).strip()
        base = override or solver_profile(self.solver)["command"]
        arguments = self.arguments.get(ctx).strip()
        command = f"{base} {arguments}".strip() if arguments else base
        timeout = float(self.timeout_hours.get(ctx) or 0.0) * 3600.0
        code, output = await run_solver(ctx, self.solver, command,
                                        workdir=ctx.workdir, timeout=timeout)
        self.exit_code_to.set(code, ctx)
        self.output_to.set(output, ctx)
        if code != 0:
            raise RuntimeError(f"{self.solver.upper()} solver failed "
                               f"(exit code {code})")
