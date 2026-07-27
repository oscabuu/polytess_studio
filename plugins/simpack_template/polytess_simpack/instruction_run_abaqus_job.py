# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetBool, PropertyGetNumber,
                                    PropertyGetPath, PropertyGetString,
                                    PropertySetNumber)
from polytess.library.instructions.instruction_run_command import RunCommand


@meta(title="Run Abaqus Job", category="Abaqus/Run Abaqus Job",
      icon="terminal", color="red",
      description="Submits an Abaqus job (abaqus job=... input=...) and waits",
      parameters=(("Job Name", "The Abaqus job name"),
                  ("Input File", "The .inp input deck"),
                  ("Cpus", "Number of CPUs"),
                  ("Interactive", "Wait for completion (interactive switch)")),
      keywords=("fem", "solver", "inp", "job"))
class RunAbaqusJob(Instruction):

    def __init__(self, job: str = "job1", input_file: str = ""):
        super().__init__()
        # TODO: adapt to your abaqus command / license setup
        self.abaqus = PropertyGetPath("abaqus")
        self.job = PropertyGetString(job)
        self.input_file = PropertyGetPath(input_file)
        self.cpus = PropertyGetNumber(4)
        self.interactive = PropertyGetBool(True)
        self.check_exit_code = PropertyGetBool(True)
        self.exit_code_to = PropertySetNumber()

    @property
    def title(self) -> str:
        return f"Abaqus job {self.job} ({self.input_file})"

    async def run(self, ctx):
        parts = [f'"{self.abaqus.get(ctx)}"',
                 f"job={self.job.get(ctx)}",
                 f'input="{ctx.resolve_path(self.input_file.get(ctx))}"',
                 f"cpus={int(self.cpus.get(ctx))}"]
        if self.interactive.get(ctx):
            parts.append("interactive")
        command = RunCommand()
        command.command = PropertyGetString(" ".join(parts))
        command.check_exit_code = self.check_exit_code
        command.exit_code_to = self.exit_code_to
        command._parent = self._parent
        await command.run(ctx)
