# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Render a template file: replace variable placeholders and write the result.

Supports configurable delimiters so one instruction covers all template
dialects: ``{name}`` (default, with format specs), ``#name#`` (legacy
training templates) and ``{{name}}`` (legacy Abaqus/FEMFAT decks)."""

from __future__ import annotations

import os
import re

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetPath, format_with_variables


def render_template_text(text: str, ctx, open_delimiter: str = "{",
                         close_delimiter: str = "}") -> tuple[str, int]:
    """Replace placeholders with graph/global variables (plus {target},
    {workdir}). Returns (rendered text, number of replacements).
    Unknown names stay as-is so typos remain visible."""
    if open_delimiter == "{" and close_delimiter == "}":
        rendered = format_with_variables(text, ctx)
        return rendered, -1        # -1 = count not tracked by format_map

    pattern = re.compile(re.escape(open_delimiter) + r"([A-Za-z0-9_\-]+)"
                         + re.escape(close_delimiter))
    count = 0

    def _pretty(value):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def lookup(match: re.Match) -> str:
        nonlocal count
        name = match.group(1)
        if name == "target":
            count += 1
            return _pretty(ctx.target)
        if name == "workdir":
            count += 1
            return ctx.workdir
        scope = ctx.graph_variables
        if scope is not None and scope.exists(name):
            count += 1
            return _pretty(scope.get(name))
        if ctx.globals.variables.exists(name):
            count += 1
            return _pretty(ctx.globals.variables.get(name))
        return match.group(0)

    return pattern.sub(lookup, text), count


@meta(title="Render Template File", category="Files/Render Template File", icon="file",
      color="yellow",
      description="Copies a template file replacing placeholders with graph/"
                  "global variables. Delimiters are configurable: {name} "
                  "(default), #name# (legacy), {{name}} (legacy decks)",
      parameters=(("Template", "Source template file"),
                  ("Destination", "Output file"),
                  ("Open/Close Delimiter", "Placeholder markers around the name"),
                  ("Fail On Unresolved", "Error if placeholders remain")),
      keywords=("template", "input", "generate", "placeholder", "subvar", "deck"))
class RenderTemplateFile(Instruction):
    FIELD_CHOICES = {"open_delimiter": ["{", "#", "{{", "<", "%"],
                     "close_delimiter": ["}", "#", "}}", ">", "%"]}

    def __init__(self, template: str = "", destination: str = "",
                 open_delimiter: str = "{", close_delimiter: str = "}"):
        super().__init__()
        self.template = PropertyGetPath(template)
        self.destination = PropertyGetPath(destination)
        self.open_delimiter = open_delimiter
        self.close_delimiter = close_delimiter
        self.fail_on_unresolved = PropertyGetBool(False)

    @property
    def title(self) -> str:
        marker = f"{self.open_delimiter}…{self.close_delimiter}"
        return f"Render template {self.template} -> {self.destination} ({marker})"

    async def run(self, ctx):
        src = ctx.resolve_path(self.template.get(ctx))
        dst = ctx.resolve_path(self.destination.get(ctx))
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        rendered, _count = render_template_text(text, ctx, self.open_delimiter,
                                                self.close_delimiter)
        if self.fail_on_unresolved.get(ctx):
            pattern = re.compile(re.escape(self.open_delimiter)
                                 + r"([A-Za-z0-9_\-]+)"
                                 + re.escape(self.close_delimiter))
            leftover = sorted(set(pattern.findall(rendered)))
            if leftover:
                raise ValueError(f"Unresolved placeholders in {src}: "
                                 f"{', '.join(leftover)}")
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(rendered)
        ctx.info(f"Rendered template {src} -> {dst}")
