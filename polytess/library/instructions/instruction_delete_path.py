# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

import os
import shutil
from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Delete File / Folder", category="Files/Delete", icon="trash", color="red",
      description="Deletes a file or an entire directory tree",
      keywords=("remove", "rm", "rmtree"))
class DeletePath(Instruction):

    FIELD_HELP = {
        "path": "File or folder to delete; relative paths resolve against "
                "the working directory. Folders are removed with their "
                "entire contents.",
        "missing_ok": "If enabled (default), a non-existing path is silently "
                      "ignored; if disabled, the step fails with a "
                      "file-not-found error.",
    }

    def __init__(self, path: str = "", missing_ok: bool = True):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.missing_ok = PropertyGetBool(missing_ok)

    @property
    def title(self) -> str:
        return f"Delete {self.path}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        if os.path.isdir(path):
            shutil.rmtree(path)
            ctx.info(f"Deleted folder {path}")
        elif os.path.isfile(path):
            os.remove(path)
            ctx.info(f"Deleted file {path}")
        elif not self.missing_ok.get(ctx):
            raise FileNotFoundError(path)
