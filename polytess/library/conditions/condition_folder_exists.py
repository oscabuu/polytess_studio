# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: eine Klasse pro Datei (siehe Vorlage)."""

from __future__ import annotations

import os
from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetPath


@meta(title="Folder Exists", category="Files/Folder Exists", icon="folder", color="blue",
      description="True if the path points to an existing directory")
class FolderExists(Condition):

    def __init__(self, path: str = ""):
        super().__init__()
        self.path = PropertyGetPath(path)

    @property
    def summary(self) -> str:
        return f"folder exists {self.path}"

    def run(self, ctx):
        return os.path.isdir(ctx.resolve_path(self.path.get(ctx)))
