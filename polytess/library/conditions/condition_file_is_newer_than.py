# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath


@meta(title="File Is Newer Than", category="Files/File Is Newer Than", icon="clock",
      color="blue",
      description="True if file A was modified after file B (rebuild checks)")
class FileIsNewerThan(Condition):

    def __init__(self, file_a: str = "", file_b: str = ""):
        super().__init__()
        self.file_a = PropertyGetPath(file_a)
        self.file_b = PropertyGetPath(file_b)

    @property
    def summary(self) -> str:
        return f"{self.file_a} newer than {self.file_b}"

    def run(self, ctx):
        a = ctx.resolve_path(self.file_a.get(ctx))
        b = ctx.resolve_path(self.file_b.get(ctx))
        if not os.path.exists(a):
            return False
        if not os.path.exists(b):
            return True
        return os.path.getmtime(a) > os.path.getmtime(b)
