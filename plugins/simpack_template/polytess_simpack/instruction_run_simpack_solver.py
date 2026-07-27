# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetBool, PropertyGetPath,
                                    PropertyGetString, PropertySetNumber)
from polytess.library.instructions.instruction_run_command import RunCommand


@meta(title="Run Simpack Solver", category="Simpack/Run Simpack Solver",
      icon="terminal", color="red",
      description="Runs simpack-slv on a model file and waits for completion",
      parameters=(("Solver", "Path to simpack-slv executable"),
                  ("Model", "The .spck model file"),
                  ("Extra Arguments", "Additional command line switches")),
      keywords=("mbs", "solver", "simulation", "spck"))
class RunSimpackSolver(Instruction):

    def __init__(self, model: str = ""):
        super().__init__()
        # TODO: adapt default install path / module environment for your site
        self.solver = PropertyGetPath("simpack-slv")
        self.model = PropertyGetPath(model)
        self.extra_arguments = PropertyGetString("")
        self.check_exit_code = PropertyGetBool(True)
        self.exit_code_to = PropertySetNumber()

    @property
    def title(self) -> str:
        return f"Simpack solve {self.model}"

    async def run(self, ctx):
        command = RunCommand()
        command.command = PropertyGetString(
            f'"{self.solver.get(ctx)}" {self.extra_arguments.get(ctx)} '
            f'"{ctx.resolve_path(self.model.get(ctx))}"'.strip())
        command.check_exit_code = self.check_exit_code
        command.exit_code_to = self.exit_code_to
        command._parent = self._parent
        await command.run(ctx)
