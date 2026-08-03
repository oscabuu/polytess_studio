# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Short hash of a string (unique job identifiers)."""

from __future__ import annotations

import hashlib
import time

from polytess.core.instructions import Instruction
from polytess.core.metadata import meta
from polytess.core.properties import PropertyGetBool, PropertyGetString, PropertySetString


@meta(title="Compute Hash", category="Text/Compute Hash", icon="number", color="teal",
      description="MD5 hash (first N characters) of a text — with optional "
                  "timestamp salt for unique job IDs",
      keywords=("md5", "id", "unique", "job"))
class ComputeHash(Instruction):

    FIELD_HELP = {
        "source": "Text to hash (supports variable sources); its MD5 digest "
                  "is truncated to the requested length.",
        "length": "Number of hex characters kept from the MD5 digest "
                  "(default 10, minimum 1) — shorter IDs are easier to read "
                  "but less unique.",
        "add_timestamp_salt": "If enabled (default), the current time in "
                              "milliseconds is appended to the text before "
                              "hashing, so every run yields a fresh, unique "
                              "ID even for identical input.",
        "target": "String variable that receives the resulting hash; the "
                  "value is written into the chosen graph/global variable.",
    }

    def __init__(self, source: str = "", length: int = 10):
        super().__init__()
        self.source = PropertyGetString(source)
        self.length = length
        self.add_timestamp_salt = PropertyGetBool(True)
        self.target = PropertySetString()

    @property
    def title(self) -> str:
        return f"Set {self.target} = hash({self.source})[:{self.length}]"

    async def run(self, ctx):
        text = self.source.get(ctx)
        if self.add_timestamp_salt.get(ctx):
            text = f"{text}_{int(time.time() * 1000)}"
        digest = hashlib.md5(text.encode()).hexdigest()[:max(1, int(self.length))]
        self.target.set(digest, ctx)
