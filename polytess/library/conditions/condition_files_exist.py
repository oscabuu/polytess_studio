# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Condition: all/any paths of a list exist (fan-in check)."""

from __future__ import annotations

import os

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetList


@meta(title="Files Exist", category="Files/Files Exist", icon="file", color="blue",
      description="True if all (or any) paths in a list exist",
      keywords=("all", "any", "batch", "results"))
class FilesExist(Condition):
    FIELD_CHOICES = {"mode": ["all", "any"]}

    FIELD_HELP = {
        "list": "List variable holding the paths to check; relative paths "
                "resolve against the working directory. An empty or "
                "missing list makes the condition false.",
        "mode": "\"all\" is true only when every path exists; \"any\" is "
                "true as soon as at least one path exists.",
        "sign": "Polarity of the check: enabled means \"If\" (result used "
                "as is), disabled means \"Not\" (result inverted).",
    }

    LEGACY_ALIASES = {"list_name": "list"}

    def __init__(self, list_name: str | list = "", mode: str = "all"):
        super().__init__()
        self.list = PropertyGetList(list_name)
        self.mode = mode

    @property
    def summary(self) -> str:
        return f"{self.mode} files in {self.list.display} exist"

    def run(self, ctx):
        items = self.list.get(ctx)
        if not items:
            return False
        checks = (os.path.exists(ctx.resolve_path(str(p))) for p in items)
        return all(checks) if self.mode == "all" else any(checks)
