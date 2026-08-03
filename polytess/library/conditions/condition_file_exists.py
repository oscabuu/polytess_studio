# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath


@meta(title="File Exists", category="Files/File Exists", icon="file", color="blue",
      description="True if the path points to an existing file")
class FileExists(Condition):

    FIELD_HELP = {
        "path": "File to check; relative paths resolve against the working "
                "directory. True only for an existing regular file, not a "
                "folder.",
        "sign": "Polarity of the check: enabled means \"If\" (result used "
                "as is), disabled means \"Not\" (result inverted).",
    }

    def __init__(self, path: str = ""):
        super().__init__()
        self.path = PropertyGetPath(path)

    @property
    def summary(self) -> str:
        return f"file exists {self.path}"

    def run(self, ctx):
        return os.path.isfile(ctx.resolve_path(self.path.get(ctx)))
