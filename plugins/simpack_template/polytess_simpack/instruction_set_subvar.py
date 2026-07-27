# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Auto-split: one class per file (see the plugin template)."""

from __future__ import annotations

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import (PropertyGetBool, PropertyGetPath,
                                    PropertyGetString, PropertySetNumber)


@meta(title="Set Subvar", category="Simpack/Set Subvar", icon="edit", color="yellow",
      description="Changes a $_SUBVAR value inside a .subvar file "
                  "(simple text substitution — adapt to your file format)",
      keywords=("parameter", "variation", "doe"))
class SetSubvar(Instruction):

    def __init__(self, file: str = "", subvar: str = "", value: str = ""):
        super().__init__()
        self.file = PropertyGetPath(file)
        self.subvar = PropertyGetString(subvar)
        self.value = PropertyGetString(value)

    @property
    def title(self) -> str:
        return f"Set subvar {self.subvar} = {self.value}"

    async def run(self, ctx):
        import re
        path = ctx.resolve_path(self.file.get(ctx))
        name = self.subvar.get(ctx)
        value = self.value.get(ctx)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # TODO: adjust the pattern to your subvar syntax
        pattern = re.compile(rf"(subvar\(\s*\{{?\s*{re.escape(name)}[^,]*,\s*str\s*=\s*')[^']*(')",
                             re.IGNORECASE)
        text, count = pattern.subn(rf"\g<1>{value}\g<2>", text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        ctx.info(f"SetSubvar: {count} substitution(s) for {name} in {path}")
