# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (
    PropertyGetBool, PropertyGetPath, PropertyGetString, PropertySetString,
    format_with_variables,
)


@meta(title="Replace In File", category="Files/Replace In File", icon="edit", color="yellow",
      description="Search & replace inside a text file (input-file modification)",
      keywords=("sed", "substitute", "modify", "input"))
class ReplaceInFile(Instruction):

    FIELD_HELP = {
        "path": "Text file to modify in place (UTF-8); relative paths "
                "resolve against the working directory.",
        "search": "Literal text to look for (no regex); every "
                  "occurrence in the file is replaced.",
        "replace": "Replacement text written for each occurrence; the "
                   "number of replacements is reported in the log.",
    }

    def __init__(self, path: str = "", search: str = "", replace: str = ""):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.search = PropertyGetString(search)
        self.replace = PropertyGetString(replace)

    @property
    def title(self) -> str:
        return f"Replace {self.search} -> {self.replace} in {self.path}"

    async def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        count = text.count(self.search.get(ctx))
        text = text.replace(self.search.get(ctx), self.replace.get(ctx))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        ctx.info(f"Replaced {count} occurrence(s) in {path}")
