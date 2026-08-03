# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Condition: a text file contains a string (e.g. 'error' in a solver log)."""

from __future__ import annotations

import os

from polytess.core.conditions import Condition
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetPath, PropertyGetString


@meta(title="File Contains Text", category="Files/File Contains Text", icon="search",
      color="blue",
      description="True if the file exists and contains the text "
                  "(optionally case-insensitive)",
      keywords=("grep", "log", "error", "search"))
class FileContainsText(Condition):

    FIELD_HELP = {
        "path": "Text file to search; relative paths resolve against the "
                "working directory. A missing file makes the condition "
                "false.",
        "text": "Text to look for anywhere in the file; the condition is "
                "true when it is found.",
        "ignore_case": "If enabled (default), the search ignores upper/"
                       "lower case; if disabled, the match is exact.",
        "sign": "Polarity of the check: enabled means \"If\" (result used "
                "as is), disabled means \"Not\" (result inverted).",
    }

    def __init__(self, path: str = "", text: str = ""):
        super().__init__()
        self.path = PropertyGetPath(path)
        self.text = PropertyGetString(text)
        self.ignore_case = PropertyGetBool(True)

    @property
    def summary(self) -> str:
        return f"{self.path} contains {self.text}"

    def run(self, ctx):
        path = ctx.resolve_path(self.path.get(ctx))
        if not os.path.isfile(path):
            return False
        needle = self.text.get(ctx)
        with open(path, encoding="utf-8", errors="replace") as fh:
            haystack = fh.read()
        if self.ignore_case.get(ctx):
            return needle.lower() in haystack.lower()
        return needle in haystack
