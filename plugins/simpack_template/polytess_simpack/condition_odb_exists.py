# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetBool, PropertyGetNumber,
                                    PropertyGetPath, PropertyGetString,
                                    PropertySetNumber)


@meta(title="Odb Exists", category="Abaqus/Odb Exists", icon="file", color="blue",
      description="True if the job's .odb result file exists")
class OdbExists(Condition):

    def __init__(self, job: str = "job1", directory: str = ""):
        super().__init__()
        self.job = PropertyGetString(job)
        self.directory = PropertyGetPath(directory)

    @property
    def summary(self) -> str:
        return f"odb of {self.job} exists"

    def run(self, ctx):
        directory = ctx.resolve_path(self.directory.get(ctx) or ctx.workdir)
        return os.path.isfile(os.path.join(directory, f"{self.job.get(ctx)}.odb"))
