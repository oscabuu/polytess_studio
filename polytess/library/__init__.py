# Copyright (c) 2026 Winthir Studios.
# Licensed under the Business Source License 1.1 — see LICENSE.txt.
# Converts to Apache License 2.0 on 2030-07-27.
"""Built-in generic library of Instructions, Conditions and Events.

One source file per class:
    instructions/instruction_<name>.py
    conditions/condition_<name>.py
    events/event_<name>.py

All modules in these folders are discovered and imported AUTOMATICALLY —
adding a new file is enough, no import line needed. Files starting with
an underscore are skipped (templates, helpers).

Domain plugins (Simpack, Abaqus, ...) register additional types via the
``polytess.plugins`` entry point group.
"""

from __future__ import annotations

import importlib
import pkgutil


def import_all_modules(package_name: str) -> list[str]:
    """Import every non-underscore module in *package_name* (recursively
    usable by plugins too). Returns the imported module names."""
    package = importlib.import_module(package_name)
    imported = []
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{package_name}.{info.name}")
        imported.append(info.name)
    return imported


for _sub in ("instructions", "conditions", "events"):
    import_all_modules(f"polytess.library.{_sub}")
